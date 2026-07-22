package com.welove.shop.trade.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.trade.dto.CreateOrderRequest;
import com.welove.shop.trade.service.OrderService;
import com.welove.shop.trade.vo.OrderVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 订单 Controller。
 * <p>
 * 全部需登录。
 */
@RestController
@RequestMapping("/order")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    /** 下单。 */
    @PostMapping("/create")
    public Result<OrderVO> create(@Valid @RequestBody CreateOrderRequest request) {
        return Result.ok(orderService.createOrder(UserContext.requireUserId(), request));
    }

    /** 分页查订单。 */
    @GetMapping("/list")
    public Result<IPage<OrderVO>> list(
            @RequestParam(required = false) Integer status,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return Result.ok(orderService.listOrders(UserContext.requireUserId(), status, page, size));
    }

    /** 订单详情。 */
    @GetMapping("/{id}")
    public Result<OrderVO> detail(@PathVariable Long id) {
        return Result.ok(orderService.getOrderDetail(UserContext.requireUserId(), id));
    }

    /** 支付。 */
    @PutMapping("/{id}/pay")
    public Result<Void> pay(@PathVariable Long id) {
        orderService.payOrder(UserContext.requireUserId(), id);
        return Result.ok();
    }

    /** 取消。 */
    @PutMapping("/{id}/cancel")
    public Result<Void> cancel(@PathVariable Long id) {
        orderService.cancelOrder(UserContext.requireUserId(), id);
        return Result.ok();
    }

    /** 确认收货。 */
    @PutMapping("/{id}/receive")
    public Result<Void> receive(@PathVariable Long id) {
        orderService.confirmReceive(UserContext.requireUserId(), id);
        return Result.ok();
    }

    /** 删除订单(仅 3/4 状态)。 */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        orderService.deleteOrder(UserContext.requireUserId(), id);
        return Result.ok();
    }
}
