package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

import java.math.BigDecimal;

@FeignClient(name = "trade-service", contextId = "tradeStatsClient")
public interface TradeStatsClient {
    @GetMapping("/internal/order/count")
    Result<Long> count();

    @GetMapping("/internal/order/today-revenue")
    Result<BigDecimal> todayRevenue();
}
