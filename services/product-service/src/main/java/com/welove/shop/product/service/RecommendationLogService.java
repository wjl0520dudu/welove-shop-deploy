package com.welove.shop.product.service;

import com.welove.shop.product.entity.RecommendationLog;

/**
 * AI 商品推荐日志服务。
 * <p>
 * 由 chat-service(或前端点击回调)写入,供离线分析 + 推荐算法迭代。
 */
public interface RecommendationLogService {

    /** 写入一条推荐日志。 */
    RecommendationLog save(RecommendationLog log);

    /** 更新用户反馈(feedback: 1=满意, 0=不满意)。 */
    void updateFeedback(Long id, Integer feedback);

    /** 标记用户已点击该推荐。 */
    void markClicked(Long id);
}
