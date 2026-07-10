package com.welove.shop.product.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.product.entity.RecommendationLog;
import com.welove.shop.product.service.RecommendationLogService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * AI 商品推荐日志 Controller。
 * <p>
 * 三个端点:
 * <ul>
 *   <li>POST /api/recommend-log — chat-service 生成推荐后回写日志</li>
 *   <li>PUT  /api/recommend-log/{id}/click — 用户点击推荐(前端埋点回调)</li>
 *   <li>PUT  /api/recommend-log/{id}/feedback?value=0|1 — 用户反馈满意度</li>
 * </ul>
 * 全部需登录(userId 在日志体里由调用方传,前后端约定)。
 */
@RestController
@RequestMapping("/api/recommend-log")
@RequiredArgsConstructor
public class RecommendationLogController {

    private final RecommendationLogService service;

    @PostMapping
    public Result<RecommendationLog> save(@RequestBody RecommendationLog log) {
        return Result.ok(service.save(log));
    }

    @PutMapping("/{id}/click")
    public Result<Void> click(@PathVariable Long id) {
        service.markClicked(id);
        return Result.ok();
    }

    @PutMapping("/{id}/feedback")
    public Result<Void> feedback(@PathVariable Long id, @RequestParam Integer value) {
        service.updateFeedback(id, value);
        return Result.ok();
    }
}
