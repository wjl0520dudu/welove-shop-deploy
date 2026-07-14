package com.welove.shop.product.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.product.entity.RecommendationLog;
import com.welove.shop.product.mapper.RecommendationLogMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * 内部管理后台接口 —— 推荐效果统计 + 日志查询。
 * <p>供 admin-bff 通过 Feign 调用,直接操作 Mapper。</p>
 * <p>userClicked: 1=点击, 0=未点击</p>
 * <p>userFeedback: 1=满意, 0=不满意, null=未反馈</p>
 */
@RestController
@RequestMapping("/internal/admin/recommend")
@RequiredArgsConstructor
public class InternalAdminRecommendController {

    private final RecommendationLogMapper recommendationLogMapper;

    /** 推荐效果统计。 */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        Map<String, Object> result = new HashMap<>();
        long total = recommendationLogMapper.selectCount(null);

        long clicked = recommendationLogMapper.selectCount(
                Wrappers.lambdaQuery(RecommendationLog.class)
                        .eq(RecommendationLog::getUserClicked, 1));

        long satisfied = recommendationLogMapper.selectCount(
                Wrappers.lambdaQuery(RecommendationLog.class)
                        .eq(RecommendationLog::getUserFeedback, 1));

        long dissatisfied = recommendationLogMapper.selectCount(
                Wrappers.lambdaQuery(RecommendationLog.class)
                        .eq(RecommendationLog::getUserFeedback, 0));

        long noFeedback = total - satisfied - dissatisfied;

        result.put("totalRecommendations", total);
        result.put("clickRate", total > 0 ? Math.round(clicked * 100.0 / total) : 0);
        result.put("satisfactionRate", total > 0 ? Math.round(satisfied * 100.0 / total) : 0);
        result.put("noFeedbackRate", total > 0 ? Math.round(noFeedback * 100.0 / total) : 0);
        result.put("clickedCount", clicked);
        result.put("satisfiedCount", satisfied);
        result.put("noFeedbackCount", noFeedback);

        return Result.ok(result);
    }

    /** 分页查询推荐日志。 */
    @GetMapping("/logs")
    public Result<IPage<RecommendationLog>> logs(@RequestParam(defaultValue = "1") int page,
                                                  @RequestParam(defaultValue = "20") int size) {
        LambdaQueryWrapper<RecommendationLog> wrapper = Wrappers.lambdaQuery(RecommendationLog.class)
                .orderByDesc(RecommendationLog::getCreateTime);
        return Result.ok(recommendationLogMapper.selectPage(new Page<>(page, size), wrapper));
    }
}
