package com.welove.shop.product.vo;

import com.welove.shop.product.entity.Product;
import com.welove.shop.product.entity.ProductFaq;
import com.welove.shop.product.entity.ProductImage;
import com.welove.shop.product.entity.ProductReview;
import com.welove.shop.product.entity.ProductSku;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

/**
 * 商品详情聚合 VO。
 * <p>
 * GET /api/product/{id} 返回:
 * <ul>
 *   <li>{@code product}  — 商品主表字段</li>
 *   <li>{@code skus}     — SKU 列表</li>
 *   <li>{@code images}   — 图片列表</li>
 *   <li>{@code faqs}     — FAQ 列表(可选)</li>
 *   <li>{@code reviews}  — 评价列表(仅取前 N 条,默认 10)</li>
 * </ul>
 */
@Data
public class ProductDetailVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Product product;
    private List<ProductSku> skus;
    private List<ProductImage> images;
    private List<ProductFaq> faqs;
    private List<ProductReview> reviews;
}
