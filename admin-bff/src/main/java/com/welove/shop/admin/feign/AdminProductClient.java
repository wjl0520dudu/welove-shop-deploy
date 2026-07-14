package com.welove.shop.admin.feign;

import com.welove.shop.common.core.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * product-service admin 内部接口 Feign 客户端。
 * <p>包含商品管理 + 推荐效果统计(推荐日志数据在 product_svc)。</p>
 */
@FeignClient(name = "product-service", contextId = "adminProductClient")
public interface AdminProductClient {

    // ================ 商品管理 ================

    @GetMapping("/internal/admin/product/list")
    Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") int page,
                                     @RequestParam(defaultValue = "20") int size,
                                     @RequestParam(required = false) String keyword,
                                     @RequestParam(required = false) Long categoryId,
                                     @RequestParam(required = false) String brand,
                                     @RequestParam(required = false) Integer status,
                                     @RequestParam(required = false) Double minPrice,
                                     @RequestParam(required = false) Double maxPrice,
                                     @RequestParam(defaultValue = "id") String sortBy,
                                     @RequestParam(defaultValue = "desc") String sortOrder);

    @PostMapping("/internal/admin/product")
    Result<Map<String, Object>> create(@RequestBody Map<String, Object> product);

    @PutMapping("/internal/admin/product/{id}/status")
    Result<Void> updateStatus(@PathVariable("id") Long id, @RequestParam("status") int status);

    @PutMapping("/internal/admin/product/{id}")
    Result<Map<String, Object>> update(@PathVariable("id") Long id, @RequestBody Map<String, Object> product);

    @GetMapping("/internal/admin/product/stats")
    Result<Map<String, Object>> stats();

    @GetMapping("/internal/admin/product/brands")
    Result<List<String>> brands();

    // ================ 推荐日志(product_svc) ================

    @GetMapping("/internal/admin/recommend/stats")
    Result<Map<String, Object>> recommendStats();

    @GetMapping("/internal/admin/recommend/logs")
    Result<Map<String, Object>> recommendLogs(@RequestParam(defaultValue = "1") int page,
                                              @RequestParam(defaultValue = "20") int size);
}
