package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class AgentStepDTO implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private String id;
    private String runId;
    private String stepName;
    private String status;
    private String input;
    private String output;
    private String errorMessage;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private LocalDateTime createdAt;
}
