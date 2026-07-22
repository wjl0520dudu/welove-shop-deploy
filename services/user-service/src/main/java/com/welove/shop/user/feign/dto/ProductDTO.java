package com.welove.shop.user.feign.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * Feign 从 product-service 拿商品基础字段的接收 DTO。
 * <p>
 * 只保留 user 域需要的字段(title/imageUrl/basePrice),不引 product-service 的完整 entity。
 * MyBatis-Plus 相关注解在 Feign 客户端侧无意义,已省略。
 */
@Data
public class ProductDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long id;
    private String title;
    private String imageUrl;
    private BigDecimal basePrice;
    /** 1=上架,0=下架。user 域用于决定是否给商品卡片打「已下架」灰显。 */
    private Integer status;
}