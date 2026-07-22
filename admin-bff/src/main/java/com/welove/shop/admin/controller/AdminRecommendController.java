package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminProductClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 管理端推荐效果统计 —— Feign 透传 product-service /internal/admin/recommend。
 * <p>推荐日志表 recommendation_log 位于 product_svc schema。</p>
 */
@RestController
@RequestMapping("/recommend")
@RequiredArgsConstructor
public class AdminRecommendController {

    private final AdminProductClient product;

    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        return product.recommendStats();
    }

    @GetMapping("/logs")
    public Result<Map<String, Object>> logs(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "20") int size) {
        return product.recommendLogs(page, size);
    }
}
