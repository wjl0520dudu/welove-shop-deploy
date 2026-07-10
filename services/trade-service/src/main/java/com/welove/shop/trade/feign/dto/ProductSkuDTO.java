package com.welove.shop.trade.feign.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Map;

/**
 * Feign 从 product-service 拿 SKU 字段的接收 DTO。
 */
@Data
public class ProductSkuDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long id;
    private Long productId;
    private String skuCode;
    private Map<String, String> properties;
    private BigDecimal price;
    private Integer stock;
    private Integer isDefault;
}
