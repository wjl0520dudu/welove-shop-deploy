package com.welove.shop.chat.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.chat.mapper.ConversationMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 内部统计接口 —— 供 admin-bff Dashboard Feign 调用。
 */
@RestController
@RequestMapping("/internal/conversation")
@RequiredArgsConstructor
public class InternalConversationController {

    private final ConversationMapper conversationMapper;

    /** 对话总数。 */
    @GetMapping("/count")
    public Result<Long> count() {
        return Result.ok(conversationMapper.selectCount(null));
    }
}
