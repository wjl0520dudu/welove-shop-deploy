package com.welove.shop.product.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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

    @Override
    public List<Category> listActive() {
        return categoryMapper.selectList(
                new LambdaQueryWrapper<Category>()
                        .eq(Category::getIsActive, 1)
                        .orderByAsc(Category::getSortOrder));
    }

    @Override
    public Category getById(Long id) {
        return categoryMapper.selectById(id);
    }
}
