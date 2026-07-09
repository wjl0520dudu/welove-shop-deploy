package com.welove.shop.user.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品收藏实体。
 * <p>
 * (user_id, product_id) 上有唯一索引,防止重复收藏。
 * <p>
 * productName/productImage/productPrice 三个字段为跨服务展示字段,骨架期不填,
 * 后续通过 Feign 调 product-service 补齐(TODO)。
 */
@Data
@TableName("user_favorite")
public class UserFavorite implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long productId;

    private LocalDateTime createTime;

    // ---------- 非数据库字段:Product 冗余展示,TODO Ph 后续 Feign 补 ----------
    @TableField(exist = false)
    private String productName;

    @TableField(exist = false)
    private String productImage;

    @TableField(exist = false)
    private BigDecimal productPrice;
}
