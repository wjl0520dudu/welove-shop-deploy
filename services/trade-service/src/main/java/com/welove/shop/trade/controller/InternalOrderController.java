package com.welove.shop.trade.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.trade.entity.Order;
import com.welove.shop.trade.mapper.OrderMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 内部统计接口 —— 供 admin-bff Dashboard Feign 调用。
 */
@RestController
@RequestMapping("/internal/order")
@RequiredArgsConstructor
public class InternalOrderController {

    private final OrderMapper orderMapper;

    /** 订单总数。 */
    @GetMapping("/count")
    public Result<Long> count() {
        return Result.ok(orderMapper.selectCount(null));
    }

    /** 今日营收(已完成订单 pay_amount 之和,status=3)。 */
    @GetMapping("/today-revenue")
    public Result<BigDecimal> todayRevenue() {
        LocalDateTime start = LocalDate.now().atStartOfDay();
        List<Order> orders = orderMapper.selectList(
                new LambdaQueryWrapper<Order>()
                        .eq(Order::getStatus, 3)
                        .ge(Order::getPayTime, start));
        BigDecimal sum = orders.stream()
                .map(Order::getPayAmount)
                .filter(java.util.Objects::nonNull)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        return Result.ok(sum);
    }
}
