package com.welove.shop.user.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.user.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 内部统计接口 —— 供 admin-bff Dashboard Feign 调用。
 * <p>
 * 路径 /api/internal/user/** 全部走白名单,不校验 JWT(骨架期)。
 */
@RestController
@RequestMapping("/internal/user")
@RequiredArgsConstructor
public class InternalUserController {

    private final UserMapper userMapper;

    /** 用户总数。 */
    @GetMapping("/count")
    public Result<Long> count() {
        return Result.ok(userMapper.selectCount(null));
    }
}
