package com.welove.shop.chat.service;

import com.welove.shop.chat.dto.AgentRunResponse;
import com.welove.shop.chat.entity.AgentRun;
import java.util.List;

public interface AgentRunService {
    AgentRun save(AgentRun run);
    AgentRun getByRunId(String runId);
    List<AgentRun> listByPage(int page, int size, String status);
    AgentRun getWithSteps(String runId);
    void deleteRun(String runId);
}
