package com.welove.shop.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.user.entity.UserFavorite;
import com.welove.shop.user.mapper.UserFavoriteMapper;
import com.welove.shop.user.service.UserFavoriteService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class UserFavoriteServiceImpl implements UserFavoriteService {

    private final UserFavoriteMapper mapper;

    @Override
    public void addFavorite(Long userId, Long productId) {
        UserFavorite existing = mapper.selectOne(
                new LambdaQueryWrapper<UserFavorite>()
                        .eq(UserFavorite::getUserId, userId)
                        .eq(UserFavorite::getProductId, productId));
        if (existing != null) {
            return;   // 幂等
        }
        UserFavorite fav = new UserFavorite();
        fav.setUserId(userId);
        fav.setProductId(productId);
        fav.setCreateTime(LocalDateTime.now());
        mapper.insert(fav);
    }

    @Override
    public void removeFavorite(Long userId, Long productId) {
        mapper.delete(
                new LambdaQueryWrapper<UserFavorite>()
                        .eq(UserFavorite::getUserId, userId)
                        .eq(UserFavorite::getProductId, productId));
    }

    @Override
    public List<UserFavorite> listByUserId(Long userId) {
        // 骨架期不填 productName/image/price,由 Feign 补齐(TODO Ph 后续)
        return mapper.selectList(
                new LambdaQueryWrapper<UserFavorite>()
                        .eq(UserFavorite::getUserId, userId)
                        .orderByDesc(UserFavorite::getCreateTime));
    }
}
