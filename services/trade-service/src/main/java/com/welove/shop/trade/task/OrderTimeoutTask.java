package com.welove.shop.trade.task;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.trade.entity.Order;
import com.welove.shop.trade.mapper.OrderMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 订单超时定时任务。
 * <p>
 * 每分钟扫一次 {@code trade-service.order.timeout-scan-cron},将 status=0 且超过
 * {@code trade-service.order.pay-timeout-minutes} 的订单自动置为 4(已取消)。
 * <p>
 * <b>说明:</b>不同于 monolith,微服务架构下下单本身不扣库存(与 monolith 行为对齐),
 * 因此超时取消时也无需"恢复库存"。这段逻辑随之删除。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OrderTimeoutTask {

    private final OrderMapper orderMapper;

    @Value("${trade-service.order.pay-timeout-minutes:10}")
    private long payTimeoutMinutes;

    /** 每分钟第 0 秒扫一次。cron 从 yml 读,方便调整。 */
    @Scheduled(cron = "${trade-service.order.timeout-scan-cron:0 * * * * ?}")
    @Transactional
    public void cancelExpiredOrders() {
        LocalDateTime deadline = LocalDateTime.now().minusMinutes(payTimeoutMinutes);
        List<Order> expired = orderMapper.selectList(
                new LambdaQueryWrapper<Order>()
                        .eq(Order::getStatus, 0)
                        .le(Order::getCreateTime, deadline));
        if (expired.isEmpty()) {
            return;
        }
        LocalDateTime now = LocalDateTime.now();
        for (Order order : expired) {
            order.setStatus(4);
            order.setUpdateTime(now);
            orderMapper.updateById(order);
        }
        log.info("[order-timeout] cancelled {} orders older than {} min", expired.size(), payTimeoutMinutes);
    }
}
