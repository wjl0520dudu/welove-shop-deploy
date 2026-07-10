package com.welove.shop.product.service;

import com.welove.shop.product.entity.ProductSku;

import java.util.List;

/**
 * 商品 SKU 服务。
 */
public interface ProductSkuService {

    /** 查某商品所有 SKU,默认规格排前。 */
    List<ProductSku> listByProductId(Long productId);

    /** 库存加减(quantity 正加负减,原子操作)。 */
    int updateStock(Long skuId, Integer quantity);
}
