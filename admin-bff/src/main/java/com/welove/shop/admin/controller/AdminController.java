package com.welove.shop.admin.controller;

import com.welove.shop.admin.dto.LoginRequest;
import com.welove.shop.admin.service.AdminService;
import com.welove.shop.common.core.result.Result;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 管理端 Controller —— 登录 + Dashboard 入口。
 * <p>
 * {@code /login} 免鉴权,其他需 role=ADMIN。
 * 网关 StripPrefix=2 剥离 /api/admin,故此 Controller 收 /login。
 */
@RestController
@RequestMapping("")
@RequiredArgsConstructor
public class AdminController {

    private final AdminService adminService;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        return Result.ok(adminService.login(request));
    }
}
