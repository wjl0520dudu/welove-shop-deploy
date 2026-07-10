package com.welove.shop.chat.controller;

import com.welove.shop.chat.dto.AgentRunRequest;
import com.welove.shop.chat.dto.AgentRunResponse;
import com.welove.shop.chat.entity.AgentRun;
import com.welove.shop.chat.service.AgentRunService;
import com.welove.shop.chat.service.AgentService;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/agent")
@RequiredArgsConstructor
public class AgentController {
    private final AgentService agentService;
    private final AgentRunService runService;

    @PostMapping("/run") public Result<AgentRunResponse> run(@RequestBody AgentRunRequest req) {
        return Result.ok(agentService.runAgent(req));
    }
    @GetMapping("/runs") public Result<List<AgentRun>> list(@RequestParam(defaultValue = "1") int pageNum, @RequestParam(defaultValue = "20") int pageSize, @RequestParam(required = false) String status) {
        return Result.ok(runService.listByPage(pageNum, pageSize, status));
    }
    @GetMapping("/run/{runId}") public Result<AgentRun> detail(@PathVariable String runId) {
        return Result.ok(runService.getWithSteps(runId));
    }
    @DeleteMapping("/run/{runId}") public Result<Void> delete(@PathVariable String runId) {
        runService.deleteRun(runId); return Result.ok();
    }
}
