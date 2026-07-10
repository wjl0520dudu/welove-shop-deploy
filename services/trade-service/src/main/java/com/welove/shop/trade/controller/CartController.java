package com.welove.shop.trade.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.common.security.context.UserContext;
import com.welove.shop.trade.service.CartService;
import com.welove.shop.trade.vo.CartItemVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 购物车 Controller。
 * <p>
 * 所有接口需登录(userId 从 UserContext 拿)。
 */
@RestController
@RequestMapping("/cart")
@RequiredArgsConstructor
public class CartController {

    private final CartService cartService;

    /** 添加商品(quantity 默认 1)。 */
    @PostMapping("/add")
    public Result<Void> add(@RequestParam Long productId,
                            @RequestParam(required = false) Long skuId,
                            @RequestParam(defaultValue = "1") Integer quantity) {
        cartService.addItem(UserContext.requireUserId(), productId, skuId, quantity);
        return Result.ok();
    }

    /** 按 productId 移除;传 quantity 则递减,不传则全删。 */
    @DeleteMapping("/remove")
    public Result<Void> remove(@RequestParam Long productId,
                               @RequestParam(required = false) Integer quantity) {
        Long userId = UserContext.requireUserId();
        if (quantity == null || quantity <= 0) {
            cartService.removeByProduct(userId, productId);
        } else {
            cartService.decreaseQuantity(userId, productId, quantity);
        }
        return Result.ok();
    }

    /** 按主键删除购物车条目。 */
    @DeleteMapping("/removeById")
    public Result<Void> removeById(@RequestParam Long cartItemId) {
        cartService.removeByCartItemId(UserContext.requireUserId(), cartItemId);
        return Result.ok();
    }

    /** 更新数量。 */
    @PutMapping("/update")
    public Result<Void> update(@RequestParam Long productId,
                               @RequestParam Integer quantity) {
        cartService.updateQuantity(UserContext.requireUserId(), productId, quantity);
        return Result.ok();
    }

    /** 切换 SKU 规格。 */
    @PutMapping("/updateSku")
    public Result<Void> updateSku(@RequestParam Long productId,
                                  @RequestParam(required = false) Long oldSkuId,
                                  @RequestParam Long newSkuId) {
        cartService.updateSku(UserContext.requireUserId(), productId, oldSkuId, newSkuId);
        return Result.ok();
    }

    /** 购物车列表(含商品/SKU 信息,Feign 补齐)。 */
    @GetMapping("/list")
    public Result<List<CartItemVO>> list() {
        return Result.ok(cartService.listWithProductByUserId(UserContext.requireUserId()));
    }

    /** 购物车条目数量。 */
    @GetMapping("/count")
    public Result<Long> count() {
        return Result.ok(cartService.getCount(UserContext.requireUserId()));
    }
}
