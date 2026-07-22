package com.welove.shop.product.controller;

import com.welove.shop.common.core.exception.BizException;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.product.entity.Category;
import com.welove.shop.product.exception.ProductErrorCode;
import com.welove.shop.product.service.CategoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品分类 Controller。
 * <p>
 * 全部匿名可访问(商品浏览无需登录)。
 */
@RestController
@RequestMapping("/category")
@RequiredArgsConstructor
public class CategoryController {

    private final CategoryService categoryService;

    @GetMapping("/list")
    public Result<List<Category>> list() {
        return Result.ok(categoryService.listActive());
    }

    @GetMapping("/{id}")
    public Result<Category> getById(@PathVariable Long id) {
        Category category = categoryService.getById(id);
        if (category == null) {
            throw new BizException(ProductErrorCode.CATEGORY_NOT_FOUND, "分类不存在");
        }
        return Result.ok(category);
    }
}
