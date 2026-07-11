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

                // SSE 事件收集 (数组引用供 lambda 内修改)
                StringBuilder answerBuilder = new StringBuilder();
                String[] taskType = {""};
                java.util.List<Map<String, Object>>[] productCards = new java.util.List[]{new java.util.ArrayList<>()};
                Map<String, Object>[] confirmCard = new Map[]{null};
                Map<String, Object>[] cartSelection = new Map[]{null};
                String[] sources = {""};

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
                    try {
                        String eventType = sse.event() != null ? sse.event() : "message";
                        String data = sse.data();
                        if (data == null || data.isEmpty()) return;

                        // 透传给前端(保留正确的事件名 + 原始 data JSON)。
                        // 上游 done 不透传:chat-service 在 doOnComplete 统一补发带 messageId 的 done,避免前端收到两个 done。
                        if (!"done".equals(eventType)) {
                            emitter.send(SseEmitter.event().name(eventType).data(data));
                        }

                        // 解析 data JSON 用于持久化收集
                        Map<String, Object> event = objectMapper.readValue(data, Map.class);
                        switch (eventType) {
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
                                    sources[0] = objectMapper.writeValueAsString(event.get("sources"));
                                }
                                break;
                            case "error":
                                log.warn("AI stream error: {}", event.getOrDefault("message", ""));
                                break;
                        }
                    } catch (IOException e) {
                        log.warn("SSE parse failed: {}", e.getMessage());
                    }
                }).doOnComplete(() -> {
                    try {
                        String answer = answerBuilder.toString();
                        // 持久化 AI 消息(含 productCards / confirmCard / cartSelection)
                        Message aiMsg = new Message();
                        aiMsg.setConversationId(conversationId);
                        aiMsg.setRole("assistant");
                        aiMsg.setContent(answer.isEmpty() ? "AI 暂时无法回复,请稍后再试" : answer);
                        aiMsg.setMessageType("text");
                        aiMsg.setTaskType(taskType[0].isEmpty() ? "shopping" : taskType[0]);
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
                        // 发送 done 事件并关闭
                        emitter.send(SseEmitter.event().name("done").data(Map.of("messageId", aiMsg.getId())));
                        emitter.complete();
                    } catch (Exception e) {
                        log.error("SSE onComplete save failed", e);
                        try { emitter.send(SseEmitter.event().name("error").data(Map.of("content", e.getMessage())));
                        } catch (IOException ex) { }
                        emitter.complete();
                    }
                }).doOnError(e -> {
                    log.error("SSE stream error", e);
                    try {
                        emitter.send(SseEmitter.event().name("error").data(Map.of("content", e.getMessage())));
                    } catch (IOException ex) { }
                    emitter.complete();
                }).subscribe();
            } catch (Exception e) {
                log.error("SSE setup error", e);
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
