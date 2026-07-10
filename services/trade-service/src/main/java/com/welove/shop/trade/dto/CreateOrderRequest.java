package com.welove.shop.trade.dto;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

/**
 * 创建订单请求。
 */
@Data
public class CreateOrderRequest implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 收货地址 ID(user-service.address.id)。 */
    @NotNull(message = "收货地址不能为空")
    private Long addressId;

    /** 订单明细。 */
    @NotEmpty(message = "订单明细不能为空")
    private List<OrderItemDto> items;

    /** 订单备注。 */
    private String remark;

    /** 覆盖收货人姓名(可选,默认取地址里的)。 */
    private String receiverName;

    /** 覆盖收货人手机号(可选)。 */
    private String receiverPhone;

    @Data
    public static class OrderItemDto implements Serializable {

        @Serial
        private static final long serialVersionUID = 1L;

        @NotNull(message = "商品 ID 不能为空")
        private Long productId;

        /** SKU ID,不选规格时可为空。 */
        private Long skuId;

        @NotNull(message = "购买数量不能为空")
        private Integer quantity;
    }
}
