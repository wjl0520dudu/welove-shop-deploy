package com.welove.shop.trade.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.welove.shop.trade.dto.CreateOrderRequest;
import com.welove.shop.trade.entity.Order;
import com.welove.shop.trade.vo.OrderVO;

/**
 * 订单服务。
 * <p>
 * 状态机:0 待付款 → 1 待发货 → 2 待收货 → 3 已完成 / 4 已取消。
 */
public interface OrderService {

    /**
     * 创建订单。
     * <p>
     * 步骤:
     * <ol>
     *   <li>Feign 拿 address(user-service),写快照</li>
     *   <li>Feign 拿 product/sku(product-service),校验商品与 SKU 存在,写快照</li>
     *   <li>计算总额,插入 order + order_item</li>
     * </ol>
     * 不扣库存(与 monolith 一致)。
     */
    OrderVO createOrder(Long userId, CreateOrderRequest request);

    /** 分页查用户订单(可按 status 过滤)。 */
    IPage<OrderVO> listOrders(Long userId, Integer status, int page, int size);

    /** 订单详情(带 userId 权限校验)。 */
    OrderVO getOrderDetail(Long userId, Long orderId);

    /** 支付:0 → 1。 */
    void payOrder(Long userId, Long orderId);

    /** 取消:仅 status=0 可取消,0 → 4。 */
    void cancelOrder(Long userId, Long orderId);

    /** 确认收货:1 或 2 → 3。 */
    void confirmReceive(Long userId, Long orderId);

    /** 删除订单:仅 status=3 或 4 可删,先删明细再删订单。 */
    void deleteOrder(Long userId, Long orderId);

    /** 供 OrderTimeoutTask 使用:按 id 更新订单状态 + updateTime。 */
    void updateStatus(Order order, Integer status);
}
