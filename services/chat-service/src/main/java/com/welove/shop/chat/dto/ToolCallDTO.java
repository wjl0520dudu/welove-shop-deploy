package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class ToolCallDTO implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private String id;
    private String toolCallId;
    private String runId;
    private String toolName;
    private String inputParams;
    private String output;
    private String status;
    private Long durationMs;
    private String errorMessage;
    private LocalDateTime timestamp;
    private LocalDateTime createdAt;
}
