package com.welove.shop.trade.feign;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.trade.feign.dto.ProductDTO;
import com.welove.shop.trade.feign.dto.ProductSkuDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;

/**
 * 调 product-service 的 Feign 客户端。
 * <p>
 * 用途:
 * <ul>
 *   <li>购物车列表补齐商品/SKU 展示字段</li>
 *   <li>下单时查商品基础价 + SKU 价格/属性,写快照到 order_item</li>
 * </ul>
 * <p>
 * 骨架期 product-service 的 batch 接口在白名单里,Feign 不带 token 也能调。
 * 分层鉴权升级后,内部服务间调用要么走服务身份 token,要么加 X-Internal-Caller 头。
 */
@FeignClient(name = "product-service", contextId = "productClient")
public interface ProductClient {

    /** 批量按 ID 查商品(不聚合 sku/image/faq/review)。 */
    @GetMapping("/api/product/batch")
    Result<List<ProductDTO>> batch(@RequestParam List<Long> ids);

    /** 批量按 ID 查 SKU。 */
    @GetMapping("/api/product/sku/batch")
    Result<List<ProductSkuDTO>> skuBatch(@RequestParam List<Long> ids);
}
