package com.welove.shop.admin.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;

/**
 * Dashboard 首页统计数据。
 * <p>
 * 4 大 count + 今日营收,由 admin-bff Feign 4 个下游服务聚合。
 */
@Data
public class DashboardStats implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long userCount;
    private Long productCount;
    private Long orderCount;
    private Long conversationCount;
    private BigDecimal todayRevenue;
}
