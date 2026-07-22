package com.welove.shop.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.user.entity.UserFavorite;
import com.welove.shop.user.feign.ProductInfoEnricher;
import com.welove.shop.user.feign.dto.ProductDTO;
import com.welove.shop.user.mapper.UserFavoriteMapper;
import com.welove.shop.user.service.UserFavoriteService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserFavoriteServiceImpl implements UserFavoriteService {

    private final UserFavoriteMapper mapper;
    private final ProductInfoEnricher productEnricher;

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
        List<UserFavorite> list = mapper.selectList(
                new LambdaQueryWrapper<UserFavorite>()
                        .eq(UserFavorite::getUserId, userId)
                        .orderByDesc(UserFavorite::getCreateTime));
        if (list.isEmpty()) return list;
        // 批量调 product-service 补齐商品展示字段(title/imageUrl/basePrice)
        enrichProductFields(list);
        return list;
    }

    /**
     * 调 Feign 拿商品基础字段并回写到 @TableField(exist=false) 的 productName/image/productPrice 上。
     * Feign 调用由 ProductInfoEnricher 兜底:失败/为空时所有字段保持 null,前端走「商品已下架」占位。
     */
    private void enrichProductFields(List<UserFavorite> list) {
        Map<Long, ProductDTO> productMap = productEnricher.loadByIds(
                list.stream().map(UserFavorite::getProductId).collect(Collectors.toList()));
        for (UserFavorite fav : list) {
            ProductDTO p = productMap.get(fav.getProductId());
            if (p == null) continue;
            fav.setProductName(p.getTitle());
            fav.setProductImage(p.getImageUrl());
            fav.setProductPrice(p.getBasePrice());
        }
    }
}