package com.welove.shop.admin.service;

import com.welove.shop.admin.dto.LoginRequest;

import java.util.Map;

public interface AdminService {
    /** 管理员登录。返回 Map {accessToken, refreshToken, tokenType, admin}。 */
    Map<String, Object> login(LoginRequest request);
}
