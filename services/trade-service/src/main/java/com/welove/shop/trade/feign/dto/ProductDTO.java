package com.welove.shop.trade.feign.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * Feign 从 product-service 拿商品基础字段的接收 DTO。
 * <p>
 * 只保留 trade 域需要的字段,不引 product-service 的完整 entity(避免跨服务耦合)。
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
    private String brand;
    private Integer status;   // 1=上架,0=下架
}
