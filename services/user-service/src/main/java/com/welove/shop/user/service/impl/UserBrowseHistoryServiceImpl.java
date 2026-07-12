package com.welove.shop.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.user.entity.UserBrowseHistory;
import com.welove.shop.user.feign.ProductInfoEnricher;
import com.welove.shop.user.feign.dto.ProductDTO;
import com.welove.shop.user.mapper.UserBrowseHistoryMapper;
import com.welove.shop.user.service.UserBrowseHistoryService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserBrowseHistoryServiceImpl implements UserBrowseHistoryService {

    private final UserBrowseHistoryMapper mapper;
    private final ProductInfoEnricher productEnricher;

    @Override
    public void saveOrUpdate(UserBrowseHistory history) {
        UserBrowseHistory existing = mapper.selectOne(
                new LambdaQueryWrapper<UserBrowseHistory>()
                        .eq(UserBrowseHistory::getUserId, history.getUserId())
                        .eq(UserBrowseHistory::getProductId, history.getProductId()));
        if (existing != null) {
            existing.setCreateTime(LocalDateTime.now());
            existing.setSource(history.getSource());
            existing.setDurationSec(history.getDurationSec());
            mapper.updateById(existing);
        } else {
            history.setCreateTime(LocalDateTime.now());
            mapper.insert(history);
        }
    }

    @Override
    public List<UserBrowseHistory> listByUserId(Long userId) {
        List<UserBrowseHistory> all = mapper.selectList(
                new LambdaQueryWrapper<UserBrowseHistory>()
                        .eq(UserBrowseHistory::getUserId, userId)
                        .orderByDesc(UserBrowseHistory::getCreateTime));

        // 同一商品去重:LinkedHashMap 保留 first put,即最新一条
        Map<Long, UserBrowseHistory> unique = new LinkedHashMap<>();
        for (UserBrowseHistory h : all) {
            unique.putIfAbsent(h.getProductId(), h);
        }
        List<UserBrowseHistory> list = new ArrayList<>(unique.values());
        if (list.isEmpty()) return list;
        // 批量调 product-service 补齐商品展示字段(title/imageUrl/basePrice)
        enrichProductFields(list);
        return list;
    }

    /**
     * 调 Feign 拿商品基础字段并回写到 @TableField(exist=false) 的 productName/image/productPrice 上。
     * Feign 调用由 ProductInfoEnricher 兜底:失败/为空时所有字段保持 null,前端走「商品已下架」占位。
     */
    private void enrichProductFields(List<UserBrowseHistory> list) {
        Map<Long, ProductDTO> productMap = productEnricher.loadByIds(
                list.stream().map(UserBrowseHistory::getProductId).collect(Collectors.toList()));
        for (UserBrowseHistory h : list) {
            ProductDTO p = productMap.get(h.getProductId());
            if (p == null) continue;
            h.setProductName(p.getTitle());
            h.setProductImage(p.getImageUrl());
            h.setProductPrice(p.getBasePrice());
        }
    }

    @Override
    public void deleteHistory(Long userId, Long historyId) {
        UserBrowseHistory history = mapper.selectById(historyId);
        if (history == null) {
            throw new BizException(ErrorCode.NOT_FOUND);
        }
        if (!history.getUserId().equals(userId)) {
            throw new BizException(ErrorCode.FORBIDDEN);
        }
        mapper.deleteById(historyId);
    }
}