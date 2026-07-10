package com.welove.shop.chat.service.impl;

import com.welove.shop.chat.dto.AgentRunRequest;
import com.welove.shop.chat.dto.AgentRunResponse;
import com.welove.shop.chat.entity.AgentRun;
import com.welove.shop.chat.service.AgentRunService;
import com.welove.shop.chat.service.AgentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class AgentServiceImpl implements AgentService {
    private final AgentRunService runService;
    private final RestTemplate restTemplate;
    @Value("${ai.service.url}") private String aiUrl;

    @Override
    public AgentRunResponse runAgent(AgentRunRequest req) {
        String runId = UUID.randomUUID().toString();
        AgentRun run = new AgentRun();
        run.setRunId(runId);
        run.setTraceId(req.getTraceId());
        run.setConversationId(req.getConversationId());
        run.setUserId(req.getUserId());
        run.setGoal(req.getGoal());
        run.setInput(req.getInput());
        run.setStatus("running");
        run.setStartTime(LocalDateTime.now());
        run.setCreatedAt(LocalDateTime.now());
        runService.save(run);
        try {
            req.setRunId(runId);
            Map<String, Object> resp = restTemplate.postForObject(aiUrl + "/agent/run", req, Map.class);
            AgentRun byRun = runService.getByRunId(runId);
            if (byRun != null) {
                byRun.setStatus("completed");
                byRun.setEndTime(LocalDateTime.now());
                if (resp != null) {
                    byRun.setOutput(String.valueOf(resp.getOrDefault("output", "")));
                }
                runService.save(byRun);
            }
        } catch (Exception e) {
            log.error("[Agent] run failed: {}", e.getMessage());
            AgentRun byRun = runService.getByRunId(runId);
            if (byRun != null) { byRun.setStatus("failed"); byRun.setErrorMessage(e.getMessage()); runService.save(byRun); }
        }
        AgentRunResponse response = new AgentRunResponse();
        AgentRun finalRun = runService.getByRunId(runId);
        if (finalRun != null) {
            response.setId(finalRun.getId()); response.setRunId(finalRun.getRunId()); response.setStatus(finalRun.getStatus());
            response.setStartTime(finalRun.getStartTime()); response.setEndTime(finalRun.getEndTime());
            response.setOutput(finalRun.getOutput()); response.setErrorMessage(finalRun.getErrorMessage());
        }
        return response;
    }

    @Override public void cancelAgentRun(String runId) {
        AgentRun run = runService.getByRunId(runId);
        if (run != null) { run.setStatus("cancelled"); runService.save(run); }
    }

    @Override public AgentRunResponse retryAgentRun(String runId) {
        AgentRun orig = runService.getByRunId(runId);
        if (orig == null) return null;
        AgentRunRequest req = new AgentRunRequest();
        req.setGoal(orig.getGoal()); req.setInput(orig.getInput());
        req.setConversationId(orig.getConversationId()); req.setUserId(orig.getUserId());
        req.setTraceId(orig.getTraceId());
        return runAgent(req);
    }
}
