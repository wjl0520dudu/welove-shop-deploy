package com.welove.shop.product.service;

import com.welove.shop.product.entity.ProductFaq;

import java.util.List;

/**
 * 商品 FAQ 服务。
 */
public interface ProductFaqService {

    /** 查某商品所有 FAQ,按 sort_order 升序。 */
    List<ProductFaq> listByProductId(Long productId);
}
