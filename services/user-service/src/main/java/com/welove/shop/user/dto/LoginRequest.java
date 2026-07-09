package com.welove.shop.user.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 手机号验证码登录请求。
 */
@Data
public class LoginRequest {

    @NotBlank(message = "手机号不能为空")
    private String phone;

    @NotBlank(message = "验证码不能为空")
    private String code;

    /** 兼容旧密码登录字段(骨架期不启用密码登录)。 */
    private String password;
}
