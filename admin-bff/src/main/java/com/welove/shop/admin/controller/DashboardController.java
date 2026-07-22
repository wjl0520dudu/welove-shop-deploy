package com.welove.shop.admin.controller;

import com.welove.shop.admin.dto.DashboardStats;
import com.welove.shop.admin.service.DashboardService;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Dashboard 首页 —— 4 大 count + 今日营收。
 * <p>
 * 全部通过 Feign 聚合 4 个下游服务的内部 count 接口。
 * 网关 StripPrefix=2 剥离 /api/admin,故此 Controller 收 /dashboard。
 */
@RestController
@RequestMapping("/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    @GetMapping("/stats")
    public Result<DashboardStats> stats() {
        return Result.ok(dashboardService.getStats());
    }
}
