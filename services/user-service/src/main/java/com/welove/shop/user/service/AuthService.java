package com.welove.shop.user.service;

import com.welove.shop.user.dto.UpdateUserRequest;
import com.welove.shop.user.entity.User;

import java.util.Map;

/**
 * 用户认证与资料服务。
 */
public interface AuthService {

    /** 发送短信验证码(骨架期为 mock 模式,控制台打印)。 */
    void sendSmsCode(String phone);

    /** 手机号验证码登录;未注册手机号会自动创建账号。 */
    Map<String, Object> login(String phone, String code);

    /** 根据用户 ID 查询用户信息。 */
    User getUserById(Long userId);

    /** 根据 refresh token 换取新 access token。 */
    Map<String, Object> refreshToken(String token);

    /** 更新用户资料;仅非 null / 非空字段被写入。 */
    User updateUserInfo(UpdateUserRequest request);

    /**
     * 为指定用户生成登录响应(token + refreshToken + user + tokenType)。
     * <p>
     * 公开此方法以供 {@link TestLoginService} 等"已经有 user 实体但不需要走
     * 完整 login/sms 流程"的场景复用,避免重复 token 生成逻辑。
     */
    Map<String, Object> generateTokenResponse(User user);
}
