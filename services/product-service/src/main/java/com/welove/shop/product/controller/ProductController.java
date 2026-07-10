package com.welove.shop.product.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.product.entity.Product;
import com.welove.shop.product.service.ProductService;
import com.welove.shop.product.vo.ProductDetailVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 商品 Controller。
 * <p>
 * 商品浏览无需登录,全部走 JwtInterceptor 白名单。
 * 提交评价的接口(POST /api/product/{id}/reviews)在 ReviewController,需登录。
 */
@RestController
@RequestMapping("/api/product")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    /** 分页列表 —— 可选 categoryId 和排序。 */
    @GetMapping("/list")
    public Result<IPage<Product>> list(
            @RequestParam(required = false) Long categoryId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "sales") String sortBy,
            @RequestParam(defaultValue = "desc") String sortOrder) {
        return Result.ok(productService.listByCategory(categoryId, page, size, sortBy, sortOrder));
    }

    /** 关键词搜索(LIKE MVP,后续升级到 RAG)。 */
    @GetMapping("/search")
    public Result<List<Product>> search(
            @RequestParam String keyword,
            @RequestParam(defaultValue = "20") int limit) {
        return Result.ok(productService.search(keyword, limit));
    }

    /** 热门商品(按销量倒序)。 */
    @GetMapping("/hot")
    public Result<List<Product>> hot(@RequestParam(defaultValue = "10") int limit) {
        return Result.ok(productService.getHotProducts(limit));
    }

    /** 商品详情(聚合 sku/image/faq/review)。 */
    @GetMapping("/{id}")
    public Result<ProductDetailVO> detail(@PathVariable Long id) {
        return Result.ok(productService.getDetail(id));
    }
}
