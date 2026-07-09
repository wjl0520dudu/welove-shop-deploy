package com.welove.shop.user.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.user.entity.UserFavorite;
import com.welove.shop.user.service.UserFavoriteService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品收藏 Controller。
 * <p>
 * 收藏关系用 (userId, productId) 唯一约束,重复 POST 视为幂等。
 * 骨架期只返回 productId,Product 展示字段留给后续 Feign 补齐。
 */
@RestController
@RequestMapping("/api/user/favorites")
@RequiredArgsConstructor
public class UserFavoriteController {

    private final UserFavoriteService service;

    /** 添加收藏(幂等)。 */
    @PostMapping("/{productId}")
    public Result<Void> add(@PathVariable Long productId) {
        service.addFavorite(UserContext.requireUserId(), productId);
        return Result.ok();
    }

    /** 取消收藏。 */
    @DeleteMapping("/{productId}")
    public Result<Void> remove(@PathVariable Long productId) {
        service.removeFavorite(UserContext.requireUserId(), productId);
        return Result.ok();
    }

    /** 当前用户的收藏列表。 */
    @GetMapping
    public Result<List<UserFavorite>> list() {
        return Result.ok(service.listByUserId(UserContext.requireUserId()));
    }
}
