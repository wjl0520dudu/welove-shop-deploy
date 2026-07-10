package com.welove.shop.admin.service.impl;

import com.welove.shop.admin.dto.DashboardStats;
import com.welove.shop.admin.feign.ChatStatsClient;
import com.welove.shop.admin.feign.ProductStatsClient;
import com.welove.shop.admin.feign.TradeStatsClient;
import com.welove.shop.admin.feign.UserStatsClient;
import com.welove.shop.admin.service.DashboardService;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * Dashboard 聚合服务:通过 Feign 聚合 4 个下游服务的统计。
 * <p>
 * 温柔降级:任一 Feign 失败时对应字段返回 0(或 BigDecimal.ZERO),不阻塞整体页面渲染。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DashboardServiceImpl implements DashboardService {

    private final UserStatsClient userClient;
    private final ProductStatsClient productClient;
    private final TradeStatsClient tradeClient;
    private final ChatStatsClient chatClient;

    @Override
    public DashboardStats getStats() {
        DashboardStats stats = new DashboardStats();
        stats.setUserCount(safeCount(() -> userClient.count(), "user"));
        stats.setProductCount(safeCount(() -> productClient.count(), "product"));
        stats.setOrderCount(safeCount(() -> tradeClient.count(), "order"));
        stats.setConversationCount(safeCount(() -> chatClient.count(), "conversation"));
        stats.setTodayRevenue(safeRevenue());
        return stats;
    }

    private Long safeCount(java.util.function.Supplier<Result<Long>> call, String label) {
        try {
            Result<Long> r = call.get();
            if (r != null && r.isSuccess() && r.getData() != null) return r.getData();
        } catch (Exception e) {
            log.warn("[Dashboard] fetch {} count failed: {}", label, e.getMessage());
        }
        return 0L;
    }

    private BigDecimal safeRevenue() {
        try {
            Result<BigDecimal> r = tradeClient.todayRevenue();
            if (r != null && r.isSuccess() && r.getData() != null) return r.getData();
        } catch (Exception e) {
            log.warn("[Dashboard] fetch today-revenue failed: {}", e.getMessage());
        }
        return BigDecimal.ZERO;
    }
}
