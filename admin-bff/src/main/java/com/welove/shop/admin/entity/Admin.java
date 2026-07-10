package com.welove.shop.admin.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 管理员账号实体。
 * <p>
 * password 序列化时忽略,防止通过 /profile 泄露 BCrypt 密文。
 */
@Data
@TableName("admin")
public class Admin implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private String username;

    @JsonIgnore
    private String password;

    /** ADMIN / SUPER_ADMIN(预留)。 */
    private String role;

    private LocalDateTime createTime;
}
