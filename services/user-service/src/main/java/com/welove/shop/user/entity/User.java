package com.welove.shop.user.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 用户实体。
 * <p>
 * 表名 users(PG 保留字 user 无法直接作表名)。
 * <p>
 * preference_tags 用 JSONB 存 List&lt;String&gt;,MyBatis-Plus 通过
 * {@code JacksonTypeHandler} 完成 JSON &lt;-&gt; List 转换,{@code autoResultMap=true} 让 select 也命中该 handler。
 */
@Data
@TableName(value = "users", autoResultMap = true)
public class User implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private String username;

    private String phone;

    /** 密码。接口序列化时忽略,避免通过 /profile 泄露密文。 */
    @JsonIgnore
    private String password;

    private String avatarUrl;

    /** 0=未知, 1=男, 2=女。 */
    private Integer gender;

    /** 年龄段,如 "18-24"。 */
    private String ageRange;

    /** 肤质,如 "干皮"/"油皮"。 */
    private String skinType;

    /** 偏好标签,JSONB 列。 */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<String> preferenceTags;

    /** 1=正常, 0=禁用。 */
    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
