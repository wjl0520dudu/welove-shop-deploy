package com.welove.shop.user.service;

import com.welove.shop.user.entity.UserBrowseHistory;

import java.util.List;

/**
 * 商品浏览历史服务。
 * <p>
 * 骨架期不填充 Product 信息,只保留 productId。后续 Ph 通过 Feign 调 product-service 补齐。
 */
public interface UserBrowseHistoryService {

    /** 保存或更新浏览记录:同 user_id + product_id 的老记录会被覆盖时间/来源/时长。 */
    void saveOrUpdate(UserBrowseHistory history);

    /** 查用户的浏览历史,按创建时间倒序,同一商品只保留最新一条。 */
    List<UserBrowseHistory> listByUserId(Long userId);

    /** 删除某条记录,只有归属该 userId 的才允许删。 */
    void deleteHistory(Long userId, Long historyId);
}
