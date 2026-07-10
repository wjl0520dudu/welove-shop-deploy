package com.welove.shop.product.service.impl;

import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.product.entity.RecommendationLog;
import com.welove.shop.product.mapper.RecommendationLogMapper;
import com.welove.shop.product.service.RecommendationLogService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class RecommendationLogServiceImpl implements RecommendationLogService {

    private final RecommendationLogMapper mapper;

    @Override
    public RecommendationLog save(RecommendationLog log) {
        if (log.getCreateTime() == null) {
            log.setCreateTime(LocalDateTime.now());
        }
        if (log.getUserClicked() == null) {
            log.setUserClicked(0);
        }
        mapper.insert(log);
        return log;
    }

    @Override
    public void updateFeedback(Long id, Integer feedback) {
        RecommendationLog existing = mapper.selectById(id);
        if (existing == null) {
            throw new BizException(ErrorCode.NOT_FOUND);
        }
        existing.setUserFeedback(feedback);
        mapper.updateById(existing);
    }

    @Override
    public void markClicked(Long id) {
        RecommendationLog existing = mapper.selectById(id);
        if (existing == null) {
            throw new BizException(ErrorCode.NOT_FOUND);
        }
        existing.setUserClicked(1);
        mapper.updateById(existing);
    }
}
