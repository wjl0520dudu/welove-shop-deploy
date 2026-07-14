package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminTradeClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端订单管理 —— Feign 透传 trade-service /internal/admin/order。
 */
@RestController
@RequestMapping("/order")
@RequiredArgsConstructor
public class AdminOrderController {

    private final AdminTradeClient client;

    @GetMapping("/list")
    public Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "20") int size,
                                            @RequestParam(required = false) Long userId,
                                            @RequestParam(required = false) Integer status,
                                            @RequestParam(required = false) String orderNo,
                                            @RequestParam(required = false) String keyword) {
        return client.list(page, size, userId, status, orderNo, keyword);
    }

    @GetMapping("/{id}/items")
    public Result<List<Map<String, Object>>> items(@PathVariable Long id) {
        return client.items(id);
    }

    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        return client.stats();
    }
}
