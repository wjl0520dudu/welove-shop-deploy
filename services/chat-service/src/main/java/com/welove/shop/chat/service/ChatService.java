package com.welove.shop.chat.service;

import com.welove.shop.chat.dto.FeedbackRequest;
import com.welove.shop.chat.entity.Conversation;
import com.welove.shop.chat.entity.Message;

import java.util.List;
import java.util.Map;

public interface ChatService {
    /** 新建会话。 */
    Conversation createConversation(Long userId, String title);
    /** 历史会话列表(置顶在前)。 */
    List<Conversation> getHistory(Long userId);
    /** 消息列表(带 Redis 缓存)。 */
    List<Message> getMessages(Long conversationId);
    /** 非流式发送消息。 */
    Message sendMessage(Long userId, Long conversationId, String content, String jwtToken);
    /** 流式发送消息(SSE) —— 返回 SseEmitter,Controller 层用。 */
    org.springframework.web.servlet.mvc.method.annotation.SseEmitter sendStreamMessage(
            Long userId, Long conversationId, String content, String username,
            String jwtToken, String gender, String skinType, java.util.List<String> preferenceTags);
    /** 删除会话(级联消息)。 */
    void deleteConversation(Long conversationId);
    /** 更新会话(标题/置顶)。 */
    void updateConversation(Long conversationId, String title, Boolean isPinned);
    /** 消息反馈。 */
    void submitFeedback(FeedbackRequest request);
    /**
     * 前端 abort 时主动把半成品发到后端落库(status=truncated)。
     * 与 doOnCancel 兜底共享同一去重逻辑,clientTs 用于冲突判优。
     * 返回新插入(或已存在去重命中)的 message id。
     */
    Long persistTruncatedFromClient(Long userId, Long conversationId, String content,
                                    List<Map<String, Object>> productCards,
                                    Map<String, Object> confirmCard,
                                    Map<String, Object> cartSelection,
                                    String taskType, Long clientTs);
}
