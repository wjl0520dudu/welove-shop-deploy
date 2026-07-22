package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminProductClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端商品管理 —— Feign 透传 product-service /internal/admin/product。
 * <p>网关 StripPrefix=2 剥离 /api/admin,故此 Controller 收 /product。</p>
 */
@RestController
@RequestMapping("/product")
@RequiredArgsConstructor
public class AdminProductController {

    private final AdminProductClient client;

    @GetMapping("/list")
    public Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") int page,
                                            @RequestParam(defaultValue = "20") int size,
                                            @RequestParam(required = false) String keyword,
                                            @RequestParam(required = false) Long categoryId,
                                            @RequestParam(required = false) String brand,
                                            @RequestParam(required = false) Integer status,
                                            @RequestParam(required = false) Double minPrice,
                                            @RequestParam(required = false) Double maxPrice,
                                            @RequestParam(defaultValue = "id") String sortBy,
                                            @RequestParam(defaultValue = "desc") String sortOrder) {
        return client.list(page, size, keyword, categoryId, brand, status, minPrice, maxPrice, sortBy, sortOrder);
    }

    @PostMapping
    public Result<Map<String, Object>> create(@RequestBody Map<String, Object> product) {
        return client.create(product);
    }

    @PutMapping("/{id}/status")
    public Result<Void> updateStatus(@PathVariable Long id, @RequestParam int status) {
        return client.updateStatus(id, status);
    }

    @PutMapping("/{id}")
    public Result<Map<String, Object>> update(@PathVariable Long id, @RequestBody Map<String, Object> product) {
        return client.update(id, product);
    }

    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        return client.stats();
    }

    @GetMapping("/brands")
    public Result<List<String>> brands() {
        return client.brands();
    }
}
