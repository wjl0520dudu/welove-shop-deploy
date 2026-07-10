package com.welove.shop.product.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.welove.shop.product.entity.Product;
import com.welove.shop.product.vo.ProductDetailVO;

import java.util.List;

/**
 * 商品服务。
 */
public interface ProductService {

    /** 按分类分页查(可选 categoryId,支持 sortBy: price/rating/reviews/newest/sales)。 */
    IPage<Product> listByCategory(Long categoryId, int page, int size, String sortBy, String sortOrder);

    /** 单条查询(仅 Product 表)。 */
    Product getById(Long id);

    /** 详情聚合(product + skus + images + faqs + reviews)。 */
    ProductDetailVO getDetail(Long id);

    /** LIKE 搜索(含同义词扩展 + 相关性打分,MVP 版,后续被 RAG 向量搜索替换)。 */
    List<Product> search(String keyword, int limit);

    /** 热门商品(按销量倒序)。 */
    List<Product> getHotProducts(int limit);
}
