package com.welove.shop.user.service;

import com.welove.shop.user.entity.UserFavorite;

import java.util.List;

/**
 * 商品收藏服务。
 * <p>
 * 骨架期不填充 Product 信息,只保留 productId。后续 Ph 通过 Feign 调 product-service 补齐。
 */
public interface UserFavoriteService {

    /** 添加收藏,重复调用视为幂等(唯一索引保护 + 前置查重)。 */
    void addFavorite(Long userId, Long productId);

    /** 取消收藏。 */
    void removeFavorite(Long userId, Long productId);

    /** 查用户收藏列表,按创建时间倒序。 */
    List<UserFavorite> listByUserId(Long userId);
}
