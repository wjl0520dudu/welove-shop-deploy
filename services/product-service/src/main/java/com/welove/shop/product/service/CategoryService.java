package com.welove.shop.product.service;

import com.welove.shop.product.entity.Category;

import java.util.List;

/**
 * 商品分类服务。
 */
public interface CategoryService {

    /** 查启用分类列表(按 sort_order 升序)。 */
    List<Category> listActive();

    /** 按 ID 查分类。 */
    Category getById(Long id);
}
