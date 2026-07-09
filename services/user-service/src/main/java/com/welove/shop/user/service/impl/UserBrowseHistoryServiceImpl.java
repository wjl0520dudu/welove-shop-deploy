package com.welove.shop.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.user.entity.UserBrowseHistory;
import com.welove.shop.user.mapper.UserBrowseHistoryMapper;
import com.welove.shop.user.service.UserBrowseHistoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class UserBrowseHistoryServiceImpl implements UserBrowseHistoryService {

    private final UserBrowseHistoryMapper mapper;

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
        // 骨架期不填充 productName/image/price,由 Feign 补齐(TODO Ph 后续)
        return new ArrayList<>(unique.values());
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
