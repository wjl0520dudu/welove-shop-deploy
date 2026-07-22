package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminChatClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端 QA 日志 + 未回答问题 —— Feign 透传 chat-service /internal/admin/qa。
 */
@RestController
@RequestMapping("/qa")
@RequiredArgsConstructor
public class AdminQaController {

    private final AdminChatClient chat;

    @GetMapping("/logs")
    public Result<Map<String, Object>> logs(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "20") int size) {
        return chat.qaLogs(page, size);
    }

    @GetMapping("/unanswered/list")
    public Result<List<Map<String, Object>>> unansweredList() {
        return chat.qaUnansweredList();
    }
}
