package com.welove.shop.user.feign;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.user.feign.dto.ProductDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;

/**
 * 调 product-service 的 Feign 客户端。
 * <p>
 * 用途:补齐浏览历史 / 收藏列表里的商品名、图片、价格(原本只存 productId,前端展示靠这个 join)。
 * <p>
 * 复用 product-service 现成的 GET /product/batch,骨架期该接口已在 WebMvcConfig 白名单,
 * Feign 不带 token 也能直接调;trade-service 已在用,行为稳定。
 */
@FeignClient(name = "product-service", contextId = "userProductClient")
public interface ProductClient {

    /** 批量按 ID 查商品基础字段。 */
    @GetMapping("/product/batch")
    Result<List<ProductDTO>> batch(@RequestParam List<Long> ids);
}