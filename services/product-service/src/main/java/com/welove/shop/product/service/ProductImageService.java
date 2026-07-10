package com.welove.shop.product.service;

import com.welove.shop.product.entity.ProductImage;

import java.util.List;

/**
 * 商品图片服务。
 */
public interface ProductImageService {

    /** 查某商品所有图片,按 sort_order 升序。 */
    List<ProductImage> listByProductId(Long productId);
}
