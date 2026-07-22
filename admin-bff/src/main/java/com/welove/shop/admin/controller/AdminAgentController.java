package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminChatClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端 Agent 运行监控 —— Feign 透传 chat-service /internal/admin/agent。
 */
@RestController
@RequestMapping("/agent")
@RequiredArgsConstructor
public class AdminAgentController {

    private final AdminChatClient chat;

    @GetMapping("/runs")
    public Result<Map<String, Object>> runs(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "10") int size,
                                            @RequestParam(required = false) String status,
                                            @RequestParam(required = false) String userId) {
        return chat.agentRuns(page, size, status, userId);
    }

    @GetMapping("/runs/{runId}")
    public Result<Map<String, Object>> runDetail(@PathVariable String runId) {
        return chat.agentRunDetail(runId);
    }

    @GetMapping("/runs/{runId}/steps")
    public Result<List<Map<String, Object>>> runSteps(@PathVariable String runId) {
        return chat.agentRunSteps(runId);
    }

    @GetMapping("/tool-calls")
    public Result<Map<String, Object>> toolCalls(@RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "10") int size) {
        return chat.agentToolCalls(page, size);
    }

    @GetMapping("/tool-calls/failed")
    public Result<List<Map<String, Object>>> failedToolCalls(@RequestParam(defaultValue = "10") int limit) {
        return chat.agentFailedToolCalls(limit);
    }
}
