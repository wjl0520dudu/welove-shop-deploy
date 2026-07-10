package com.welove.shop.admin.service;

import com.welove.shop.admin.dto.DashboardStats;

public interface DashboardService {
    /** 聚合 4 大 count + 今日营收(全部 Feign)。 */
    DashboardStats getStats();
}
