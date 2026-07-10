package com.welove.shop.user.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.user.dto.LoginRequest;
import com.welove.shop.user.dto.UpdateUserRequest;
import com.welove.shop.user.entity.User;
import com.welove.shop.user.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 用户认证 Controller。
 * <p>
 * 手机验证码登录为主流程,暴露 5 个接口:
 * <ul>
 *   <li>POST /api/auth/sendCode  — 发送短信验证码(骨架期为 mock,控制台打印)</li>
 *   <li>POST /api/auth/login     — 手机号+验证码登录(未注册手机号自动创建账号)</li>
 *   <li>POST /api/auth/refresh   — 用 refresh token 换新 access token</li>
 *   <li>GET  /api/auth/profile   — 获取当前登录用户资料</li>
 *   <li>POST /api/auth/update    — 更新当前登录用户资料</li>
 * </ul>
 * 账号密码 register / changePassword 骨架期不开放,与 monolith 一致。
 */
@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    /** 发送短信验证码。 */
    @PostMapping("/sendCode")
    public Result<String> sendCode(@RequestParam String phone) {
        authService.sendSmsCode(phone);
        return Result.ok("验证码已发送");
    }

    /** 手机号验证码登录。 */
    @PostMapping("/login")
    public Result<Map<String, Object>> login(@Valid @RequestBody LoginRequest request) {
        return Result.ok(authService.login(request.getPhone(), request.getCode()));
    }

    /** 刷新 access token。 */
    @PostMapping("/refresh")
    public Result<Map<String, Object>> refreshToken(@RequestHeader("Authorization") String token) {
        return Result.ok(authService.refreshToken(token));
    }

    /** 当前登录用户的资料。 */
    @GetMapping("/profile")
    public Result<User> getProfile() {
        Long userId = UserContext.requireUserId();
        return Result.ok(authService.getUserById(userId));
    }

    /** 更新当前登录用户的资料。userId 由 JWT 解析后覆盖,请求体中的 userId 会被忽略,防越权。 */
    @PostMapping("/update")
    public Result<User> updateUserInfo(@RequestBody UpdateUserRequest request) {
        request.setUserId(UserContext.requireUserId());
        return Result.ok(authService.updateUserInfo(request));
    }
}
