package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * chat-service admin 内部接口 Feign 客户端。
 * <p>覆盖 chat-service 所有管理域:对话/知识库/公告/Agent/QA/知识巡检。</p>
 */
@FeignClient(name = "chat-service", contextId = "adminChatClient")
public interface AdminChatClient {

    // ================ 会话管理 ================

    @GetMapping("/internal/admin/conversation/list")
    Result<Map<String, Object>> conversationList(@RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "20") int size,
                                                 @RequestParam(required = false) Long userId,
                                                 @RequestParam(required = false) String keyword);

    @GetMapping("/internal/admin/conversation/{id}/messages")
    Result<List<Map<String, Object>>> conversationMessages(@PathVariable("id") Long id);

    @GetMapping("/internal/admin/conversation/stats")
    Result<Map<String, Object>> conversationStats();

    @DeleteMapping("/internal/admin/conversation/{id}")
    Result<Void> deleteConversation(@PathVariable("id") Long id);

    // ================ 公告管理 ================

    @GetMapping("/internal/admin/notice/list")
    Result<Map<String, Object>> noticeList(@RequestParam(defaultValue = "1") int page,
                                           @RequestParam(defaultValue = "10") int size);

    @PostMapping("/internal/admin/notice/add")
    Result<String> noticeAdd(@RequestBody Map<String, Object> notice);

    @PutMapping("/internal/admin/notice/update")
    Result<String> noticeUpdate(@RequestBody Map<String, Object> notice);

    @DeleteMapping("/internal/admin/notice/delete/{id}")
    Result<String> noticeDelete(@PathVariable("id") Long id);

    // ================ Agent 运行监控 ================

    @GetMapping("/internal/admin/agent/runs")
    Result<Map<String, Object>> agentRuns(@RequestParam(defaultValue = "1") int page,
                                          @RequestParam(defaultValue = "10") int size,
                                          @RequestParam(required = false) String status,
                                          @RequestParam(required = false) String userId);

    @GetMapping("/internal/admin/agent/runs/{runId}")
    Result<Map<String, Object>> agentRunDetail(@PathVariable("runId") String runId);

    @GetMapping("/internal/admin/agent/runs/{runId}/steps")
    Result<List<Map<String, Object>>> agentRunSteps(@PathVariable("runId") String runId);

    @GetMapping("/internal/admin/agent/tool-calls")
    Result<Map<String, Object>> agentToolCalls(@RequestParam(defaultValue = "1") int page,
                                               @RequestParam(defaultValue = "10") int size);

    @GetMapping("/internal/admin/agent/tool-calls/failed")
    Result<List<Map<String, Object>>> agentFailedToolCalls(@RequestParam(defaultValue = "10") int limit);

    // ================ QA 日志/未回答 ================

    @GetMapping("/internal/admin/qa/logs")
    Result<Map<String, Object>> qaLogs(@RequestParam(defaultValue = "1") int page,
                                       @RequestParam(defaultValue = "20") int size);

    @GetMapping("/internal/admin/qa/unanswered/list")
    Result<List<Map<String, Object>>> qaUnansweredList();

    // ================ 知识库管理 ================

    @GetMapping("/internal/admin/knowledge/list")
    Result<List<Map<String, Object>>> knowledgeList(@RequestParam(required = false) Long categoryId);

    @DeleteMapping("/internal/admin/knowledge/{id}")
    Result<Void> knowledgeDelete(@PathVariable("id") Long id);

    @PostMapping("/internal/admin/knowledge/retry-parse")
    Result<Void> knowledgeRetryParse(@RequestBody Map<String, Object> request);

    // ================ 知识巡检 ================

    @GetMapping("/internal/admin/knowledge-inspection/unanswered/analyze")
    Result<Map<String, Object>> inspectUnanswered(@RequestParam(defaultValue = "1") int minCount,
                                                  @RequestParam(defaultValue = "3") int clusterThreshold,
                                                  @RequestParam(required = false) String startDate,
                                                  @RequestParam(required = false) String endDate);

    @GetMapping("/internal/admin/knowledge-inspection/library/analyze")
    Result<Map<String, Object>> inspectLibrary(@RequestParam(defaultValue = "10") int minChunkLength,
                                               @RequestParam(defaultValue = "180") int outdatedDays,
                                               @RequestParam(defaultValue = "90") int unaccessedDays,
                                               @RequestParam(defaultValue = "0.8") double similarityThreshold);
}
