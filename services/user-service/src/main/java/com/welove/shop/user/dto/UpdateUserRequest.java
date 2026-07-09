package com.welove.shop.user.dto;

import lombok.Data;

import java.util.List;

/**
 * 更新用户资料请求。
 * <p>
 * 所有字段均可空,仅非 null / 非空字段会被更新;userId 由 Controller 从 JWT 解析后覆盖,
 * 忽略客户端传入,防止越权修改他人资料。
 */
@Data
public class UpdateUserRequest {

    private Long userId;

    private String username;

    /** 用于同步修改密码的场景,空则不改。 */
    private String password;

    private String avatarUrl;

    /** 0=未知, 1=男, 2=女。 */
    private Integer gender;

    /** 年龄段,如 "18-24"。 */
    private String ageRange;

    /** 肤质,如 "干皮"/"油皮"。 */
    private String skinType;

    /** 偏好标签。 */
    private List<String> preferenceTags;
}
