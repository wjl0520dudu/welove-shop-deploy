package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;

@Data
public class AgentRunRequest implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private String runId;
    private String traceId;
    private String conversationId;
    private String userId;
    private String input;
    private String goal;
    private String agentType;
    private String context;
    private Boolean isAdmin;
}
