package com.welove.shop.product.service;

import com.welove.shop.product.entity.ProductReview;

import java.util.List;

/**
 * 商品评价服务。
 */
public interface ProductReviewService {

    /** 查某商品的评价,按创建时间倒序,limit 取前 N 条。 */
    List<ProductReview> listByProductId(Long productId, int limit);

    /** 提交评价(rating 1-5, content 非空)。 */
    ProductReview submit(ProductReview review);
}
