package com.welove.shop.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.welove.shop.chat.dto.FeedbackRequest;
import com.welove.shop.chat.entity.Conversation;
import com.welove.shop.chat.entity.Message;
import com.welove.shop.chat.entity.QaLog;
import com.welove.shop.chat.mapper.ConversationMapper;
import com.welove.shop.chat.mapper.MessageMapper;
import com.welove.shop.chat.mapper.QaLogMapper;
import com.welove.shop.chat.service.AiService;
import com.welove.shop.chat.service.ConversationContextService;
import com.welove.shop.chat.service.ChatService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.publisher.Flux;

import java.io.IOException;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatServiceImpl implements ChatService {
    private static final String DEDUP_PREFIX = "chat:dedup:";
    private static final String STATUS_DONE = "done";
    private static final String STATUS_TRUNCATED = "truncated";
    private static final String STOP_USER_ABORT = "user_abort";
    private static final String STOP_SERVER = "server_error";
    /** 截断去重窗口(秒):同 conversation + 同 contentPrefix 在此窗口内只写一条。 */
    private static final int TRUNC_DEDUP_SECONDS = 60;
    private final ConversationMapper convMapper;
    private final MessageMapper msgMapper;
    private final QaLogMapper qaLogMapper;
    private final AiService aiService;
    private final ConversationContextService ctxService;
    private final StringRedisTemplate redisTemplate;
    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    @Value("${chat-service.context.dedup-window-seconds:30}") private long dedupWindow;
    @Value("${chat-service.sse.timeout:300000}") private long sseTimeout;

    // ---------- CRUD ----------
    @Override public Conversation createConversation(Long userId, String title) {
        Conversation c = new Conversation();
        c.setUserId(userId); c.setTitle(title != null ? title : "New Chat " + LocalDateTime.now());
        c.setScene("normal"); c.setIsPinned(0);
        c.setCreateTime(LocalDateTime.now()); c.setUpdateTime(LocalDateTime.now());
        convMapper.insert(c); return c;
    }
    @Override public List<Conversation> getHistory(Long userId) {
        return convMapper.selectList(new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getUserId, userId)
                .orderByDesc(Conversation::getIsPinned).orderByDesc(Conversation::getCreateTime));
    }
    @Override public List<Message> getMessages(Long conversationId) {
        return ctxService.getConversationContext(conversationId, 0);
    }
    @Override @Transactional public void deleteConversation(Long conversationId) {
        msgMapper.delete(new LambdaQueryWrapper<Message>().eq(Message::getConversationId, conversationId));
        convMapper.deleteById(conversationId);
    }
    @Override public void updateConversation(Long conversationId, String title, Boolean isPinned) {
        Conversation c = convMapper.selectById(conversationId);
        if (c != null) {
            if (title != null) c.setTitle(title);
            if (isPinned != null) c.setIsPinned(isPinned ? 1 : 0);
            c.setUpdateTime(LocalDateTime.now());
            convMapper.updateById(c);
        }
    }

    // ---------- sync ----------
    @Override @Transactional public Message sendMessage(Long userId, Long conversationId, String content, String jwtToken) {
        if (isDuplicate(conversationId, content)) return null;
        Message userMsg = saveUserMessage(conversationId, content);
        ctxService.updateConversationContext(conversationId, userId, userMsg);
        if (isFirstMessage(conversationId)) aiService.generateTitle(conversationId, content);
        long start = System.currentTimeMillis();
        Map<String, Object> aiResp = aiService.ask(content, List.of(), userId, null);
        long duration = System.currentTimeMillis() - start;
        Message aiMsg = new Message();
        aiMsg.setConversationId(conversationId); aiMsg.setRole("assistant");
        aiMsg.setContent(String.valueOf(aiResp.getOrDefault("answer", "")));
        aiMsg.setMessageType("text"); aiMsg.setTaskType(String.valueOf(aiResp.getOrDefault("task_type", "")));
        aiMsg.setCreateTime(LocalDateTime.now());
        msgMapper.insert(aiMsg);
        saveQaLog(userId, conversationId, content, aiMsg.getContent(), aiMsg.getTaskType(), duration);
        return aiMsg;
    }

    // ---------- SSE stream ----------
    @Override public SseEmitter sendStreamMessage(Long userId, Long conversationId, String content,
                                                   String username, String jwtToken,
                                                   String gender, String skinType, java.util.List<String> preferenceTags) {
        SseEmitter emitter = new SseEmitter(sseTimeout);
        // 用 AtomicBoolean 标记是否已正常完成,防止多个回调同时触发写库双写。
        java.util.concurrent.atomic.AtomicBoolean finalized = new java.util.concurrent.atomic.AtomicBoolean(false);
        // 把流式累积容器提升到闭包外,使 SseEmitter.onError/onCompletion/onTimeout 回调也能访问。
        StringBuilder answerBuilder = new StringBuilder();
        String[] taskType = {""};
        java.util.List<Map<String, Object>>[] productCards = new java.util.List[]{new java.util.ArrayList<>()};
        Map<String, Object>[] confirmCard = new Map[]{null};
        Map<String, Object>[] cartSelection = new Map[]{null};
        String[] sources = {""};

        // ============= SseEmitter 生命周期回调 =============
        // onCompletion: 流正常关闭时调用(包括 emitter.complete() 和客户端正常断开)
        // onTimeout:     SSE 超时(sseTimeout)时调用
        // onError:       客户端断开时 Tomcat 抛 IOException 触发,这是 Spring 推荐的「客户端断开」信号。
        // doOnNext 中 try-catch emitter.send() 抛 IOException + 改走 doOnCancel 的思路不可靠(Reactor 内部信号竞态),
        // 这里直接用 SseEmitter 的回调,更稳定。
        emitter.onCompletion(() -> {
            // 正常关闭路径 (emitter.complete()) 不需要再落库,doOnComplete 已经处理
            log.debug("SseEmitter onCompletion conv={}", conversationId);
        });
        emitter.onTimeout(() -> {
            // SSE 超时也当作「客户端断开」处理(可能是网络差被服务器端提前关了)
            if (finalized.compareAndSet(false, true)) {
                log.info("SseEmitter onTimeout, persist truncated conv={}", conversationId);
                persistTruncatedInternal(conversationId, answerBuilder.toString(),
                        productCards[0], confirmCard[0], cartSelection[0],
                        taskType[0], STOP_USER_ABORT);
            }
            emitter.complete();
        });
        emitter.onError((ex) -> {
            // 客户端断开 → 这是 Spring 官方推荐的「客户端断开」检测点
            if (finalized.compareAndSet(false, true)) {
                String exMsg = ex == null ? "" : ex.getMessage();
                log.info("SseEmitter onError (client likely disconnected): {}, persist truncated conv={}",
                        exMsg == null ? "(null)" : exMsg, conversationId);
                persistTruncatedInternal(conversationId, answerBuilder.toString(),
                        productCards[0], confirmCard[0], cartSelection[0],
                        taskType[0], STOP_USER_ABORT);
            }
            // 不要再调用 emitter.complete()/send(),流已断,会再次抛异常
        });

        CompletableFuture.runAsync(() -> {
            try {
                if (isDuplicate(conversationId, content)) { emitter.complete(); return; }
                saveUserMessage(conversationId, content);
                if (isFirstMessage(conversationId)) aiService.generateTitle(conversationId, content);

                // 拼 AI 请求体 —— 对齐 ai-service /api/assistant/stream 的 ChatRequest schema
                Map<String, Object> aiBody = new java.util.HashMap<>();
                aiBody.put("question", content);
                aiBody.put("conversation_id", conversationId.toString());
                aiBody.put("user_id", userId.toString());
                aiBody.put("username", username);
                aiBody.put("is_admin", false);
                if (jwtToken != null) aiBody.put("jwt_token", jwtToken);
                if (gender != null) aiBody.put("gender", gender);
                if (skinType != null) aiBody.put("skin_type", skinType);
                if (preferenceTags != null) aiBody.put("preference_tags", preferenceTags);

                // WebClient 对 text/event-stream 会自动解码 SSE，用 ServerSentEvent<String>
                // 直接拿到事件名 event() 与已解码的 data 载荷，避免手工按物理行拆帧(会丢事件名)。
                org.springframework.core.ParameterizedTypeReference<org.springframework.http.codec.ServerSentEvent<String>> sseType =
                        new org.springframework.core.ParameterizedTypeReference<>() {};
                Flux<org.springframework.http.codec.ServerSentEvent<String>> flux = webClient.post()
                        .uri("/assistant/stream")
                        .accept(org.springframework.http.MediaType.TEXT_EVENT_STREAM)
                        .bodyValue(aiBody)
                        .retrieve().bodyToFlux(sseType);

                flux.doOnNext(sse -> {
                    // emitter.send() 抛 IOException 时(客户端断开),让其自然抛到 Reactor,
                    // 配合 SseEmitter.onError 回调落库。此处只需吞掉 JSON 解析异常,不让真正
                    // 的客户端断开被掩盖成 parse failed。
                    String eventType = sse.event() != null ? sse.event() : "message";
                    String data = sse.data();
                    if (data == null || data.isEmpty()) return;

                    try {
                        // 透传给前端(保留正确的事件名 + 原始 data JSON)。
                        // 上游 done 不透传:chat-service 在 doOnComplete 统一补发带 messageId 的 done,避免前端收到两个 done。
                        if (!"done".equals(eventType)) {
                            emitter.send(SseEmitter.event().name(eventType).data(data));
                        }
                    } catch (IOException ioe) {
                        // 客户端断开:不再吞,让 Reactor 进入 doOnError 兜底
                        throw new RuntimeException(ioe);
                    }

                    // 解析 data JSON 用于持久化收集 (这里独立 try,不影响 send)
                    Map<String, Object> event;
                    try {
                        event = objectMapper.readValue(data, Map.class);
                    } catch (IOException je) {
                        log.warn("SSE data JSON parse failed: {}", je.getMessage());
                        return;
                    }
                    switch (eventType == null ? "" : eventType) {
                        case "token":
                            answerBuilder.append(event.getOrDefault("content", ""));
                            break;
                        case "route":
                            if (event.containsKey("task_type")) taskType[0] = String.valueOf(event.get("task_type"));
                            break;
                        case "final":
                            // ai-service 的 final data 即完整 AIResponse，字段在顶层(非嵌套 response)
                            if (answerBuilder.length() == 0 && event.containsKey("answer")) {
                                answerBuilder.append(event.get("answer"));
                            }
                            if (event.containsKey("task_type")) taskType[0] = String.valueOf(event.get("task_type"));
                            if (event.get("product_cards") instanceof java.util.List<?> pc) {
                                productCards[0] = (java.util.List<Map<String, Object>>) pc;
                            }
                            if (event.get("confirm_card") instanceof Map<?, ?> cc) {
                                confirmCard[0] = (Map<String, Object>) cc;
                            }
                            if (event.get("cart_selection") instanceof Map<?, ?> cs) {
                                cartSelection[0] = (Map<String, Object>) cs;
                            }
                            if (event.containsKey("sources")) {
                                try {
                                    sources[0] = objectMapper.writeValueAsString(event.get("sources"));
                                } catch (IOException ignored) { }
                            }
                            break;
                        case "error":
                            log.warn("AI stream error: {}", event.getOrDefault("message", ""));
                            break;
                    }
                }).doOnComplete(() -> {
                    if (!finalized.compareAndSet(false, true)) return;
                    try {
                        String answer = answerBuilder.toString();
                        // 持久化 AI 消息(含 productCards / confirmCard / cartSelection)
                        Message aiMsg = new Message();
                        aiMsg.setConversationId(conversationId);
                        aiMsg.setRole("assistant");
                        aiMsg.setContent(answer.isEmpty() ? "AI 暂时无法回复,请稍后再试" : answer);
                        aiMsg.setMessageType("text");
                        aiMsg.setTaskType(taskType[0].isEmpty() ? "shopping" : taskType[0]);
                        aiMsg.setStatus(STATUS_DONE);
                        if (!productCards[0].isEmpty()) {
                            aiMsg.setProductCards(productCards[0]);
                        }
                        if (confirmCard[0] != null) {
                            aiMsg.setConfirmCard(confirmCard[0]);
                        }
                        if (cartSelection[0] != null) {
                            aiMsg.setCartSelection(cartSelection[0]);
                        }
                        aiMsg.setSources(sources[0].isEmpty() ? null : sources[0]);
                        aiMsg.setCreateTime(LocalDateTime.now());
                        msgMapper.insert(aiMsg);
                        saveQaLog(userId, conversationId, content, answer, taskType[0].isEmpty() ? "shopping" : taskType[0], 0L);
                        // 发送 done 事件并关闭 (set finalized 已在上面 compareAndSet 完成)
                        emitter.send(SseEmitter.event().name("done").data(Map.of("messageId", aiMsg.getId())));
                        emitter.complete();
                    } catch (Exception e) {
                        log.error("SSE onComplete save failed", e);
                        // finalize 已 true,onError 不会再触发;但要发 error 给前端(如果连接还在)
                        try {
                            emitter.send(SseEmitter.event().name("error").data(Map.of("content", e.getMessage())));
                        } catch (IOException ex) { }
                        emitter.complete();
                    }
                }).doOnError(e -> {
                    // Reactor 链上报错:不是客户端断开(已由 emitter.onError 兜底),
                    // 而是 ai-service 自身出错 / 网络异常等真正的服务端问题。
                    // 注意:即使客户端断开,WebClient 的上游 reader.read() 在 Reactor 内部也会走 doOnError,
                    // 所以这里需要再次兜底,避免与 emitter.onError 双写(finalized 已经保证只写一次)。
                    if (!finalized.compareAndSet(false, true)) {
                        log.debug("Reactor doOnError but already finalized (handled by emitter.onError) conv={}", conversationId);
                        return;
                    }
                    log.error("SSE stream error (ai-service upstream)", e);
                    String answer = answerBuilder.toString();
                    Long errId = persistTruncatedInternal(conversationId, answer,
                            productCards[0], confirmCard[0], cartSelection[0],
                            taskType[0], STOP_SERVER);
                    try {
                        Map<String, Object> payload = new java.util.HashMap<>();
                        payload.put("content", String.valueOf(e.getMessage()));
                        if (errId != null) payload.put("messageId", errId);
                        emitter.send(SseEmitter.event().name("error").data(payload));
                    } catch (IOException ex) { }
                    emitter.complete();
                }).subscribe();
            } catch (Exception e) {
                log.error("SSE setup error", e);
                if (finalized.compareAndSet(false, true)) {
                    persistTruncatedInternal(conversationId, "", null, null, null, "", STOP_SERVER);
                }
                try {
                    emitter.send(SseEmitter.event().name("error").data(Map.of("content", e.getMessage())));
                    emitter.complete();
                } catch (IOException ex) { emitter.completeWithError(ex); }
            }
        });
        return emitter;
    }

    // ---------- 反馈 ----------
    @Override public void submitFeedback(FeedbackRequest req) {
        Message msg = msgMapper.selectById(req.getMessageId());
        if (msg != null) {
            msg.setFeedbackType(req.getFeedbackType()); msg.setFeedbackTime(LocalDateTime.now());
            msgMapper.updateById(msg);
            // 同步 QaLog
            List<QaLog> logs = qaLogMapper.selectList(
                    new LambdaQueryWrapper<QaLog>().eq(QaLog::getConversationId, msg.getConversationId())
                            .orderByDesc(QaLog::getCreateTime).last("LIMIT 1"));
            if (!logs.isEmpty()) { QaLog l = logs.get(0); l.setFeedbackType(req.getFeedbackType()); l.setFeedbackTime(LocalDateTime.now()); qaLogMapper.updateById(l); }
        }
    }

    // ---------- 截断持久化（双保险：前端 POST + 后端 doOnCancel） ----------
    @Override @Transactional public Long persistTruncatedFromClient(Long userId, Long conversationId, String content,
                                                                     List<Map<String, Object>> productCards,
                                                                     Map<String, Object> confirmCard,
                                                                     Map<String, Object> cartSelection,
                                                                     String taskType, Long clientTs) {
        return persistTruncatedInternal(conversationId, content, productCards, confirmCard, cartSelection, taskType, STOP_USER_ABORT);
    }

    /**
     * 截断消息落库,被前端 stop 接口与后端 Flux.doOnCancel 共用。
     * 去重策略:同 conversation + 同 content 前缀 + 60s 内已有 truncated 记录 → 跳过。
     * 返回新插入(或去重命中已存在)的 message id;content 为空时跳过(避免空消息)。
     */
    private Long persistTruncatedInternal(Long conversationId, String content,
                                          List<Map<String, Object>> productCards,
                                          Map<String, Object> confirmCard,
                                          Map<String, Object> cartSelection,
                                          String taskType, String stoppedReason) {
        log.info("[truncated] enter persistTruncatedInternal conv={} reason={} contentLen={}",
                conversationId, stoppedReason, content == null ? 0 : content.length());
        if (content == null || content.isEmpty()) {
            log.info("skip persist truncated: empty content conv={}", conversationId);
            return null;
        }
        try {
            String prefix = content.length() > 32 ? content.substring(0, 32) : content;
            // 在 Java 端拼好 LIKE pattern,避免 PG 推断 CONCAT(?) 参数类型失败
            String contentLike = prefix + "%";
            Message dup = msgMapper.selectRecentTruncated(conversationId, contentLike, TRUNC_DEDUP_SECONDS);
            if (dup != null) {
                log.info("truncated dedup hit, skip insert conv={} existingId={}", conversationId, dup.getId());
                return dup.getId();
            }
            Message aiMsg = new Message();
            aiMsg.setConversationId(conversationId);
            aiMsg.setRole("assistant");
            aiMsg.setContent(content);
            aiMsg.setMessageType("text");
            aiMsg.setTaskType(taskType == null || taskType.isEmpty() ? "shopping" : taskType);
            aiMsg.setStatus(STATUS_TRUNCATED);
            aiMsg.setStoppedReason(stoppedReason);
            aiMsg.setStoppedAt(LocalDateTime.now());
            if (productCards != null && !productCards.isEmpty()) aiMsg.setProductCards(productCards);
            if (confirmCard != null) aiMsg.setConfirmCard(confirmCard);
            if (cartSelection != null) aiMsg.setCartSelection(cartSelection);
            aiMsg.setCreateTime(LocalDateTime.now());
            log.info("[truncated] before insert conv={} contentLen={}", conversationId, content.length());
            msgMapper.insert(aiMsg);
            log.info("persisted truncated assistant conv={} id={} reason={} len={}",
                    conversationId, aiMsg.getId(), stoppedReason, content.length());
            return aiMsg.getId();
        } catch (Exception e) {
            // 任何异常都吞掉并打日志,避免中断 SseEmitter 回调线程
            log.error("[truncated] persist failed conv={} reason={}", conversationId, stoppedReason, e);
            return null;
        }
    }

    // ---------- 私有 ----------
    private boolean isDuplicate(Long convId, String content) {
        String key = DEDUP_PREFIX + convId + ":" + content.hashCode();
        Boolean ok = redisTemplate.opsForValue().setIfAbsent(key, "1", Duration.ofSeconds(dedupWindow));
        return Boolean.FALSE.equals(ok);
    }
    private Message saveUserMessage(Long convId, String content) {
        Message m = new Message();
        m.setConversationId(convId); m.setRole("user"); m.setContent(content);
        m.setMessageType("text"); m.setCreateTime(LocalDateTime.now());
        msgMapper.insert(m);
        return m;
    }
    private boolean isFirstMessage(Long convId) {
        return msgMapper.selectCount(new LambdaQueryWrapper<Message>()
                .eq(Message::getConversationId, convId)) <= 1;
    }
    private void saveQaLog(Long userId, Long convId, String question, String answer, String taskType, long duration) {
        QaLog log = new QaLog();
        log.setUserId(userId); log.setConversationId(convId);
        log.setQuestion(question); log.setAnswer(answer);
        log.setTaskType(taskType); log.setDurationMs(duration);
        log.setCreateTime(LocalDateTime.now());
        qaLogMapper.insert(log);
    }
}
