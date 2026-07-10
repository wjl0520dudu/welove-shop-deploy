package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class AgentRunResponse implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private String id;
    private String runId;
    private String traceId;
    private String conversationId;
    private String userId;
    private String status;
    private String goal;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private LocalDateTime createdAt;
    private String input;
    private String output;
    private String errorMessage;
    private String errorCode;
    private Integer currentStepIndex;
    private Integer maxSteps;
    private Integer timeoutSeconds;
    private Long elapsedTime;
    private List<AgentStepDTO> steps;
    private List<ToolCallDTO> toolCalls;
    private List<IntermediateConclusionDTO> intermediateConclusions;
    private String taskType;
    private String answer;
    private List<SourceDTO> sources;
    private Boolean hasSources;
}
