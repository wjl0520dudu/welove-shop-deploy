package com.welove.shop.user.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.user.entity.UserBrowseHistory;
import com.welove.shop.user.service.UserBrowseHistoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品浏览历史 Controller。
 * <p>
 * 骨架期只返回 productId,不填充 Product 展示字段(TODO Ph 后续 Feign 补齐)。
 */
@RestController
@RequestMapping("/browse-history")
@RequiredArgsConstructor
public class UserBrowseHistoryController {

    private final UserBrowseHistoryService service;

    /** 上报或刷新一条浏览记录。 */
    @PostMapping
    public Result<Void> report(@RequestBody UserBrowseHistory history) {
        history.setUserId(UserContext.requireUserId());
        service.saveOrUpdate(history);
        return Result.ok();
    }

    /** 查询当前用户的浏览历史(去重,倒序)。 */
    @GetMapping
    public Result<List<UserBrowseHistory>> list() {
        return Result.ok(service.listByUserId(UserContext.requireUserId()));
    }

    /** 删除某条浏览记录。 */
    @DeleteMapping("/{historyId}")
    public Result<Void> delete(@PathVariable Long historyId) {
        service.deleteHistory(UserContext.requireUserId(), historyId);
        return Result.ok();
    }
}
