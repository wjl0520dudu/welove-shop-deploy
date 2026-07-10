package com.welove.shop.product.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Map;

/**
 * 商品 SKU(规格)实体。
 * <p>
 * {@code properties} 为 JSONB 列,存 {"容量": "30ml", "颜色": "红"} 之类,
 * 通过 {@link JacksonTypeHandler} 完成 Map &lt;-&gt; JSONB 转换。
 * autoResultMap=true 让 select 也走该 handler。
 */
@Data
@TableName(value = "product_sku", autoResultMap = true)
public class ProductSku implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long productId;

    /** SKU 编码,全局唯一。 */
    private String skuCode;

    /** 规格键值,如 {"容量":"30ml"},JSONB 列。 */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, String> properties;

    private BigDecimal price;

    private Integer stock;

    /** 1=默认规格, 0=非默认(与 monolith TINYINT(1) 对齐)。 */
    private Integer isDefault;

    private LocalDateTime createTime;
}
