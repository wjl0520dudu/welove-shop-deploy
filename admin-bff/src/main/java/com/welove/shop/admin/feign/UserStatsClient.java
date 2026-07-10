package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(name = "user-service", contextId = "userStatsClient")
public interface UserStatsClient {
    @GetMapping("/api/internal/user/count")
    Result<Long> count();
}
