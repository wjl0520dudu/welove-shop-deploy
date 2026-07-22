package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminChatClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 管理端知识巡检 —— Feign 透传 chat-service /internal/admin/knowledge-inspection。
 */
@RestController
@RequestMapping("/knowledge-inspection")
@RequiredArgsConstructor
public class AdminKnowledgeInspectionController {

    private final AdminChatClient chat;

    @GetMapping("/unanswered/analyze")
    public Result<Map<String, Object>> analyzeUnanswered(@RequestParam(defaultValue = "1") int minCount,
                                                          @RequestParam(defaultValue = "3") int clusterThreshold,
                                                          @RequestParam(required = false) String startDate,
                                                          @RequestParam(required = false) String endDate) {
        return chat.inspectUnanswered(minCount, clusterThreshold, startDate, endDate);
    }

    @GetMapping("/library/analyze")
    public Result<Map<String, Object>> analyzeLibrary(@RequestParam(defaultValue = "10") int minChunkLength,
                                                       @RequestParam(defaultValue = "180") int outdatedDays,
                                                       @RequestParam(defaultValue = "90") int unaccessedDays,
                                                       @RequestParam(defaultValue = "0.8") double similarityThreshold) {
        return chat.inspectLibrary(minChunkLength, outdatedDays, unaccessedDays, similarityThreshold);
    }
}
