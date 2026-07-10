package com.welove.shop.chat.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.chat.entity.AgentRun;
import com.welove.shop.chat.entity.AgentStep;
import com.welove.shop.chat.mapper.AgentRunMapper;
import com.welove.shop.chat.mapper.AgentStepMapper;
import com.welove.shop.chat.service.AgentRunService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class AgentRunServiceImpl implements AgentRunService {
    private final AgentRunMapper runMapper;
    private final AgentStepMapper stepMapper;

    @Override public AgentRun save(AgentRun run) { runMapper.insert(run); return run; }
    @Override public AgentRun getByRunId(String runId) {
        return runMapper.selectOne(new LambdaQueryWrapper<AgentRun>().eq(AgentRun::getRunId, runId));
    }
    @Override public List<AgentRun> listByPage(int page, int size, String status) {
        LambdaQueryWrapper<AgentRun> w = new LambdaQueryWrapper<AgentRun>().orderByDesc(AgentRun::getCreatedAt);
        if (status != null && !status.isEmpty()) w.eq(AgentRun::getStatus, status);
        return runMapper.selectPage(new Page<>(page, size), w).getRecords();
    }
    @Override public AgentRun getWithSteps(String runId) {
        // steps 不在 AgentRun 实体里,由 Controller 组装
        return getByRunId(runId);
    }
    @Override public void deleteRun(String runId) {
        runMapper.delete(new LambdaQueryWrapper<AgentRun>().eq(AgentRun::getRunId, runId));
    }
}
