package com.welove.shop.trade.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * 订单明细实体。
 * <p>
 * 下单时冻结商品/SKU 快照字段(productTitle/productImage/skuProperties/price),
 * 避免后续商品下架或改价影响订单历史。
 */
@Data
@TableName("order_item")
public class OrderItem implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long orderId;

    private Long productId;

    /** 快照:下单时商品标题。 */
    private String productTitle;

    /** 快照:下单时商品图。 */
    private String productImage;

    private Long skuId;

    /** 快照:下单时 SKU 规格(如 "容量: 30ml 经典装")。 */
    private String skuProperties;

    /** 下单时快照价(优先 SKU 价格,否则商品基础价格)。 */
    private BigDecimal price;

    private Integer quantity;

    /** price * quantity。 */
    private BigDecimal totalAmount;
}
