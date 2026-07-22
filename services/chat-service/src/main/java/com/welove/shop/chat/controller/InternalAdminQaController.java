package com.welove.shop.chat.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.chat.entity.QaLog;
import com.welove.shop.chat.entity.QaUnanswered;
import com.welove.shop.chat.mapper.QaLogMapper;
import com.welove.shop.chat.mapper.QaUnansweredMapper;
import com.welove.shop.common.core.result.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 内部管理后台接口 —— QA 日志/未回答问题监控。
 * <p>供 admin-bff 调用,直接操作 Mapper 不经过 Service 层。</p>
 */
@RestController
@RequestMapping("/internal/admin/qa")
@RequiredArgsConstructor
public class InternalAdminQaController {

    private final QaLogMapper qaLogMapper;
    private final QaUnansweredMapper qaUnansweredMapper;

    /**
     * 分页查询 QA 日志,按 create_time 降序。
     */
    @GetMapping("/logs")
    public Result<IPage<QaLog>> logs(@RequestParam(defaultValue = "1") int page,
                                     @RequestParam(defaultValue = "20") int size) {
        IPage<QaLog> pageResult = qaLogMapper.selectPage(
                new Page<>(page, size),
                Wrappers.lambdaQuery(QaLog.class)
                        .orderByDesc(QaLog::getCreateTime)
        );
        return Result.ok(pageResult);
    }

    /**
     * 查询未回答问题列表,按 count 降序。
     */
    @GetMapping("/unanswered/list")
    public Result<List<QaUnanswered>> unansweredList() {
        List<QaUnanswered> list = qaUnansweredMapper.selectList(
                Wrappers.lambdaQuery(QaUnanswered.class)
                        .orderByDesc(QaUnanswered::getCount)
        );
        return Result.ok(list);
    }
}
