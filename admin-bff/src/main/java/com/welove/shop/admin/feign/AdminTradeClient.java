package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * trade-service admin 内部接口 Feign 客户端。
 * <p>订单管理相关。老的 dashboard count/revenue 保留在 TradeStatsClient。</p>
 */
@FeignClient(name = "trade-service", contextId = "adminTradeClient")
public interface AdminTradeClient {

    @GetMapping("/internal/admin/order/list")
    Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") int page,
                                     @RequestParam(defaultValue = "20") int size,
                                     @RequestParam(required = false) Long userId,
                                     @RequestParam(required = false) Integer status,
                                     @RequestParam(required = false) String orderNo,
                                     @RequestParam(required = false) String keyword);

    @GetMapping("/internal/admin/order/{id}/items")
    Result<List<Map<String, Object>>> items(@PathVariable("id") Long id);

    @GetMapping("/internal/admin/order/stats")
    Result<Map<String, Object>> stats();

    // 兼容 dashboard 的老接口
    @GetMapping("/internal/order/count")
    Result<Long> count();

    @GetMapping("/internal/order/today-revenue")
    Result<BigDecimal> todayRevenue();
}
