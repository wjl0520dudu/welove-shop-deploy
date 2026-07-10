package com.welove.shop.trade.service;

import com.welove.shop.trade.entity.UserCart;
import com.welove.shop.trade.vo.CartItemVO;

import java.util.List;

/**
 * 购物车服务。
 */
public interface CartService {

    /** 添加(同 productId+skuId 已存在则叠加数量)。 */
    void addItem(Long userId, Long productId, Long skuId, Integer quantity);

    /** 按 productId 删除该用户所有匹配行(不区分 SKU)。 */
    void removeByProduct(Long userId, Long productId);

    /** 按主键删除,附加 userId 校验。 */
    void removeByCartItemId(Long userId, Long cartItemId);

    /** 更新数量(按 userId+productId,所有匹配行) */
    void updateQuantity(Long userId, Long productId, Integer quantity);

    /** 递减数量:若剩余总量 <= quantity 则全删,否则保留第一行并更新为剩余。 */
    void decreaseQuantity(Long userId, Long productId, Integer quantity);

    /**
     * 切换 SKU:若新 SKU 已有购物车记录则合并数量并删除旧记录,
     * 否则直接把旧记录的 sku_id 换成新的。
     */
    void updateSku(Long userId, Long productId, Long oldSkuId, Long newSkuId);

    /** 查用户所有购物车原始记录(不补商品信息)。 */
    List<UserCart> listByUserId(Long userId);

    /** 查用户购物车 + Feign 补商品/SKU 展示字段。 */
    List<CartItemVO> listWithProductByUserId(Long userId);

    /** 购物车条目数量。 */
    long getCount(Long userId);
}
