package com.welove.shop.trade.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 购物车实体。
 * <p>
 * 每行 = 一条 cart item(用户维度)。同一 (userId, productId, skuId) 唯一。
 * skuId 为空表示未选规格,通过 COALESCE(sku_id, 0) 参与唯一索引。
 */
@Data
@TableName("user_cart")
public class UserCart implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long productId;

    private Long skuId;

    private Integer quantity;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
