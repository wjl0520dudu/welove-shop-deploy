package com.welove.shop.trade.vo;

import com.welove.shop.trade.entity.UserCart;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * 购物车条目展示 VO。
 * <p>
 * 从 user_cart 表基础字段 + Feign 补的商品/SKU 快照字段拼成。
 * 前端拿这个直接渲染购物车列表,不用再单独调商品接口。
 */
@Data
public class CartItemVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    // ---------- user_cart 表字段 ----------
    private Long id;
    private Long userId;
    private Long productId;
    private Long skuId;
    private Integer quantity;

    // ---------- Feign 补的展示字段 ----------
    /** 商品标题。 */
    private String productTitle;

    /** 商品主图。 */
    private String productImage;

    /** 商品基础价(SKU 未选时的兜底价格)。 */
    private BigDecimal basePrice;

    /** SKU 价格(选了 SKU 时)。 */
    private BigDecimal skuPrice;

    /** SKU 规格快照,如 "容量: 30ml"。 */
    private String skuProperties;

    /** SKU 库存(0 时前端置灰"暂时缺货")。 */
    private Integer stock;

    /** 商品状态:1=上架 / 0=下架(下架时前端置灰"已下架")。 */
    private Integer productStatus;

    /** 当前条目总价(单价 * 数量)。 */
    private BigDecimal totalPrice;

    /** 从 UserCart 基础字段填充,后续 CartService 再拼 Feign 补的字段。 */
    public static CartItemVO fromCart(UserCart cart) {
        CartItemVO vo = new CartItemVO();
        vo.setId(cart.getId());
        vo.setUserId(cart.getUserId());
        vo.setProductId(cart.getProductId());
        vo.setSkuId(cart.getSkuId());
        vo.setQuantity(cart.getQuantity());
        return vo;
    }
}
