package com.welove.shop.chat.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.chat.entity.AgentRun;
import com.welove.shop.chat.entity.AgentStep;
import com.welove.shop.chat.entity.ToolCall;
import com.welove.shop.chat.mapper.AgentRunMapper;
import com.welove.shop.chat.mapper.AgentStepMapper;
import com.welove.shop.chat.mapper.ToolCallMapper;
import com.welove.shop.common.core.exception.ErrorCode;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 内部管理后台接口 —— Agent 运行/步骤/工具调用监控。
 * <p>供 admin-bff 调用,直接操作 Mapper 不经过 Service 层。</p>
 */
@RestController
@RequestMapping("/internal/admin/agent")
@RequiredArgsConstructor
public class InternalAdminAgentController {

    private final AgentRunMapper agentRunMapper;
    private final AgentStepMapper agentStepMapper;
    private final ToolCallMapper toolCallMapper;

    /**
     * 分页查询 Agent 运行记录,按 created_at 降序。
     */
    @GetMapping("/runs")
    public Result<IPage<AgentRun>> runs(@RequestParam(defaultValue = "1") int page,
                                        @RequestParam(defaultValue = "10") int size,
                                        @RequestParam(required = false) String status,
                                        @RequestParam(required = false) String userId) {
        LambdaQueryWrapper<AgentRun> wrapper = Wrappers.lambdaQuery(AgentRun.class)
                .orderByDesc(AgentRun::getCreatedAt);
        if (status != null && !status.isBlank()) {
            wrapper.eq(AgentRun::getStatus, status);
        }
        if (userId != null && !userId.isBlank()) {
            wrapper.eq(AgentRun::getUserId, userId);
        }
        IPage<AgentRun> pageResult = agentRunMapper.selectPage(new Page<>(page, size), wrapper);
        return Result.ok(pageResult);
    }

    /**
     * 查询指定 Agent 运行详情。
     */
    @GetMapping("/runs/{runId}")
    public Result<AgentRun> runDetail(@PathVariable String runId) {
        AgentRun run = agentRunMapper.selectOne(
                Wrappers.lambdaQuery(AgentRun.class)
                        .eq(AgentRun::getRunId, runId)
        );
        if (run == null) {
            return Result.fail(ErrorCode.NOT_FOUND, "运行记录不存在");
        }
        return Result.ok(run);
    }

    /**
     * 查询指定运行的步骤列表,按 created_at 升序。
     */
    @GetMapping("/runs/{runId}/steps")
    public Result<List<AgentStep>> runSteps(@PathVariable String runId) {
        List<AgentStep> steps = agentStepMapper.selectList(
                Wrappers.lambdaQuery(AgentStep.class)
                        .eq(AgentStep::getRunId, runId)
                        .orderByAsc(AgentStep::getCreatedAt)
        );
        return Result.ok(steps);
    }

    /**
     * 分页查询工具调用记录,按 created_at 降序。
     */
    @GetMapping("/tool-calls")
    public Result<IPage<ToolCall>> toolCalls(@RequestParam(defaultValue = "1") int page,
                                             @RequestParam(defaultValue = "10") int size) {
        LambdaQueryWrapper<ToolCall> wrapper = Wrappers.lambdaQuery(ToolCall.class)
                .orderByDesc(ToolCall::getCreatedAt);
        IPage<ToolCall> pageResult = toolCallMapper.selectPage(new Page<>(page, size), wrapper);
        return Result.ok(pageResult);
    }

    /**
     * 最近失败的工具调用。
     * <p>按 status='FAILED' 或 error_message is not null 筛选,按 created_at 降序。</p>
     */
    @GetMapping("/tool-calls/failed")
    public Result<List<ToolCall>> failedToolCalls(@RequestParam(defaultValue = "10") int limit) {
        List<ToolCall> list = toolCallMapper.selectList(
                Wrappers.lambdaQuery(ToolCall.class)
                        .and(w -> w.eq(ToolCall::getStatus, "FAILED")
                                .or().isNotNull(ToolCall::getErrorMessage))
                        .orderByDesc(ToolCall::getCreatedAt)
                        .last("limit " + limit)
        );
        return Result.ok(list);
    }
}