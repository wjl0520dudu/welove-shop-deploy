package com.welove.shop.chat.controller;

import com.welove.shop.chat.dto.ChatRequest;
import com.welove.shop.chat.dto.FeedbackRequest;
import com.welove.shop.chat.dto.StreamChatRequest;
import com.welove.shop.chat.entity.Conversation;
import com.welove.shop.chat.entity.Message;
import com.welove.shop.chat.service.ChatService;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

@RestController
@RequestMapping("/chat")
@RequiredArgsConstructor
public class ChatController {
    private final ChatService chatService;

    @PostMapping("/conversations") public Result<Conversation> createConversation(@RequestParam(required = false, defaultValue = "New Chat") String title) {
        return Result.ok(chatService.createConversation(UserContext.requireUserId(), title));
    }
    @GetMapping("/conversations") public Result<List<Conversation>> getHistory() {
        return Result.ok(chatService.getHistory(UserContext.requireUserId()));
    }
    @PostMapping("/messages") public Result<Message> sendMessage(@RequestBody ChatRequest req) {
        Long uid = UserContext.requireUserId();
        Message m = chatService.sendMessage(uid, req.getConversationId(), req.getContent(), null);
        return m != null ? Result.ok(m) : Result.ok();
    }
    @PostMapping(value = "/stream/messages", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamMessages(@RequestBody StreamChatRequest req) {
        return chatService.sendStreamMessage(UserContext.requireUserId(), req.getConversationId(), req.getContent(), req.getUsername() != null ? req.getUsername() : "user", null);
    }
    @GetMapping("/messages") public Result<List<Message>> getMessages(@RequestParam Long conversationId) {
        return Result.ok(chatService.getMessages(conversationId));
    }
    @DeleteMapping("/conversations/{id}") public Result<Void> deleteConversation(@PathVariable Long id) {
        chatService.deleteConversation(id); return Result.ok();
    }
    @PutMapping("/conversations/{id}") public Result<Void> updateConversation(@PathVariable Long id, @RequestParam(required = false) String title, @RequestParam(required = false) Boolean isPinned) {
        chatService.updateConversation(id, title, isPinned); return Result.ok();
    }
    @PostMapping("/messages/feedback") public Result<Void> submitFeedback(@RequestBody FeedbackRequest req) {
        chatService.submitFeedback(req); return Result.ok();
    }
}
