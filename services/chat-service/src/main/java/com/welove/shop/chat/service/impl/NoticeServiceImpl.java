package com.welove.shop.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.chat.entity.Notice;
import com.welove.shop.chat.mapper.NoticeMapper;
import com.welove.shop.chat.service.NoticeService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class NoticeServiceImpl implements NoticeService {
    private final NoticeMapper noticeMapper;

    @Override
    public List<Notice> getActiveNotices() {
        return noticeMapper.selectList(
                new LambdaQueryWrapper<Notice>()
                        .eq(Notice::getIsActive, 1)
                        .orderByDesc(Notice::getCreateTime));
    }
}
