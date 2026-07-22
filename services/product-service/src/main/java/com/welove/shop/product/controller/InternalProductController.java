package com.welove.shop.product.controller;

import com.welove.shop.common.core.result.Result;
import com.welove.shop.product.mapper.ProductMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 内部统计接口 —— 供 admin-bff Dashboard Feign 调用。
 */
@RestController
@RequestMapping("/internal/product")
@RequiredArgsConstructor
public class InternalProductController {

    private final ProductMapper productMapper;

    /** 商品总数。 */
    @GetMapping("/count")
    public Result<Long> count() {
        return Result.ok(productMapper.selectCount(null));
    }
}
