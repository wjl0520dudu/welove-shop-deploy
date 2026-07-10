package com.welove.shop.chat.service;

import com.welove.shop.chat.dto.AgentRunRequest;
import com.welove.shop.chat.dto.AgentRunResponse;

public interface AgentService {
    AgentRunResponse runAgent(AgentRunRequest request);
    void cancelAgentRun(String runId);
    AgentRunResponse retryAgentRun(String runId);
}
