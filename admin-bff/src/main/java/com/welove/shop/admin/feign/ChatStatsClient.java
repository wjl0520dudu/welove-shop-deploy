package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(name = "chat-service", contextId = "chatStatsClient")
public interface ChatStatsClient {
    @GetMapping("/internal/conversation/count")
    Result<Long> count();
}
