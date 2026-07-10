package com.welove.shop.product.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.product.cache.ProductCache;
import com.welove.shop.product.entity.Category;
import com.welove.shop.product.mapper.CategoryMapper;
import com.welove.shop.product.service.CategoryService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class CategoryServiceImpl implements CategoryService {

    private final CategoryMapper categoryMapper;
    private final ProductCache cache;

    @Override
    public List<Category> listActive() {
        List<Category> cached = cache.getCategoryList();
        if (cached != null) {
            return cached;
        }
        List<Category> fresh = categoryMapper.selectList(
                new LambdaQueryWrapper<Category>()
                        .eq(Category::getIsActive, 1)
                        .orderByAsc(Category::getSortOrder));
        cache.putCategoryList(fresh);
        return fresh;
    }

    @Override
    public Category getById(Long id) {
        return categoryMapper.selectById(id);
    }
}
