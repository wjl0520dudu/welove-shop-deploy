package com.welove.shop.chat.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("qa_log")
public class QaLog implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO) private Long id;
    private Long userId;
    private Long conversationId;
    private String question;
    private String answer;
    private String taskType;
    private Long durationMs;
    private String feedbackType;
    private LocalDateTime feedbackTime;
    private LocalDateTime createTime;
}
