package com.welove.shop.trade.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.trade.entity.Order;
import com.welove.shop.trade.entity.OrderItem;
import com.welove.shop.trade.mapper.OrderItemMapper;
import com.welove.shop.trade.mapper.OrderMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 管理后台订单接口 —— 供 admin-bff 调用。
 */
@RestController
@RequestMapping("/internal/admin/order")
@RequiredArgsConstructor
public class InternalAdminController {

    private final OrderMapper orderMapper;
    private final OrderItemMapper orderItemMapper;

    /**
     * 分页查询订单列表。
     *
     * @param page    页码，从 1 开始
     * @param size    每页条数
     * @param userId  用户 ID（可选筛选）
     * @param status  订单状态（可选筛选）
     * @param orderNo 订单号（可选筛选）
     * @param keyword 收件人姓名/电话模糊搜索（可选）
     */
    @GetMapping("/list")
    public Result<IPage<Order>> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Integer status,
            @RequestParam(required = false) String orderNo,
            @RequestParam(required = false) String keyword) {
        QueryWrapper<Order> wrapper = new QueryWrapper<>();
        wrapper.eq(userId != null, "user_id", userId)
                .eq(status != null, "status", status)
                .eq(orderNo != null, "order_no", orderNo)
                .and(keyword != null && !keyword.isEmpty(), w ->
                        w.like("receiver_name", keyword)
                                .or()
                                .like("receiver_phone", keyword))
                .orderByDesc("create_time");
        IPage<Order> orderPage = orderMapper.selectPage(new Page<>(page, size), wrapper);
        return Result.ok(orderPage);
    }

    /**
     * 查询指定订单的商品明细。
     *
     * @param id 订单 ID
     */
    @GetMapping("/{id}/items")
    public Result<List<OrderItem>> items(@PathVariable Long id) {
        QueryWrapper<OrderItem> wrapper = new QueryWrapper<>();
        wrapper.eq("order_id", id);
        List<OrderItem> items = orderItemMapper.selectList(wrapper);
        return Result.ok(items);
    }

    /**
     * 订单统计概览。
     */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        long totalOrders = orderMapper.selectCount(null);
        long pendingPayment = orderMapper.selectCount(new QueryWrapper<Order>().eq("status", 0));
        long pendingDelivery = orderMapper.selectCount(new QueryWrapper<Order>().eq("status", 1));
        long delivered = orderMapper.selectCount(new QueryWrapper<Order>().eq("status", 2));
        long completed = orderMapper.selectCount(new QueryWrapper<Order>().eq("status", 3));
        long cancelled = orderMapper.selectCount(new QueryWrapper<Order>().eq("status", 4));

        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        long todayOrders = orderMapper.selectCount(
                new QueryWrapper<Order>().ge("create_time", todayStart));

        List<Order> completedOrders = orderMapper.selectList(
                new QueryWrapper<Order>().eq("status", 3));
        double totalRevenue = completedOrders.stream()
                .map(Order::getPayAmount)
                .filter(Objects::nonNull)
                .reduce(BigDecimal.ZERO, BigDecimal::add)
                .doubleValue();

        Map<String, Object> stats = new HashMap<>();
        stats.put("totalOrders", totalOrders);
        stats.put("pendingPayment", pendingPayment);
        stats.put("pendingDelivery", pendingDelivery);
        stats.put("delivered", delivered);
        stats.put("completed", completed);
        stats.put("cancelled", cancelled);
        stats.put("todayOrders", todayOrders);
        stats.put("totalRevenue", totalRevenue);
        return Result.ok(stats);
    }
}