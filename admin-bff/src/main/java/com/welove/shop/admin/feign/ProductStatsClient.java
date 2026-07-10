package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(name = "product-service", contextId = "productStatsClient")
public interface ProductStatsClient {
    @GetMapping("/api/internal/product/count")
    Result<Long> count();
}
