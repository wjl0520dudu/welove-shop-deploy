package com.welove.shop.admin.controller;

import com.welove.shop.admin.feign.AdminUserClient;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 管理端用户管理 —— Feign 透传 user-service /internal/admin/users。
 * <p>网关 StripPrefix=2 剥离 /api/admin,故此 Controller 收 /users。</p>
 * <p>已在 WebMvcConfig 挂 AdminInterceptor,只有 role=ADMIN 的 token 才能访问。</p>
 */
@RestController
@RequestMapping("/users")
@RequiredArgsConstructor
public class AdminUserController {

    private final AdminUserClient client;

    @GetMapping
    public Result<Map<String, Object>> list(@RequestParam(defaultValue = "1") Integer page,
                                            @RequestParam(defaultValue = "10") Integer size,
                                            @RequestParam(required = false) String keyword) {
        return client.users(page, size, keyword);
    }

    @PutMapping("/{id}/status")
    public Result<Void> updateStatus(@PathVariable Long id, @RequestParam Integer status) {
        return client.updateStatus(id, status);
    }
}
