package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminChatClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端会话管理 —— Feign 透传 chat-service /internal/admin/conversation。
 */
@RestController
@RequestMapping("/conversation")
@RequiredArgsConstructor
public class AdminConversationController {

    private final AdminChatClient chat;

    @GetMapping("/list")
    public Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "20") int size,
                                            @RequestParam(required = false) Long userId,
                                            @RequestParam(required = false) String keyword) {
        return chat.conversationList(page, size, userId, keyword);
    }

    @GetMapping("/{id}/messages")
    public Result<List<Map<String, Object>>> messages(@PathVariable Long id) {
        return chat.conversationMessages(id);
    }

    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        return chat.conversationStats();
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        return chat.deleteConversation(id);
    }
}
