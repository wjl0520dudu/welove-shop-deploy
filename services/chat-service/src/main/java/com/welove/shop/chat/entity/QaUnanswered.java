package com.welove.shop.chat.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("qa_unanswered")
public class QaUnanswered implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO) private Long id;
    private String question;
    private Integer count;
    private Long lastUserId;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
