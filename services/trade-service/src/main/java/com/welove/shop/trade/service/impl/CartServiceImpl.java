package com.welove.shop.trade.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.welove.shop.common.core.result.Result;
import com.welove.shop.trade.entity.UserCart;
import com.welove.shop.trade.feign.ProductClient;
import com.welove.shop.trade.feign.dto.ProductDTO;
import com.welove.shop.trade.feign.dto.ProductSkuDTO;
import com.welove.shop.trade.mapper.UserCartMapper;
import com.welove.shop.trade.service.CartService;
import com.welove.shop.trade.vo.CartItemVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class CartServiceImpl implements CartService {

    private final UserCartMapper cartMapper;
    private final ProductClient productClient;

    // ---------- 写入 ----------

    @Override
    @Transactional
    public void addItem(Long userId, Long productId, Long skuId, Integer quantity) {
        UserCart existing = findOne(userId, productId, skuId);
        LocalDateTime now = LocalDateTime.now();
        if (existing != null) {
            existing.setQuantity(existing.getQuantity() + quantity);
            existing.setUpdateTime(now);
            cartMapper.updateById(existing);
        } else {
            UserCart cart = new UserCart();
            cart.setUserId(userId);
            cart.setProductId(productId);
            cart.setSkuId(skuId);
            cart.setQuantity(quantity);
            cart.setCreateTime(now);
            cart.setUpdateTime(now);
            cartMapper.insert(cart);
        }
    }

    @Override
    @Transactional
    public void removeByProduct(Long userId, Long productId) {
        cartMapper.delete(
                new LambdaQueryWrapper<UserCart>()
                        .eq(UserCart::getUserId, userId)
                        .eq(UserCart::getProductId, productId));
    }

    @Override
    @Transactional
    public void removeByCartItemId(Long userId, Long cartItemId) {
        cartMapper.delete(
                new LambdaQueryWrapper<UserCart>()
                        .eq(UserCart::getId, cartItemId)
                        .eq(UserCart::getUserId, userId));
    }

    @Override
    @Transactional
    public void updateQuantity(Long userId, Long productId, Integer quantity) {
        List<UserCart> rows = cartMapper.selectList(
                new LambdaQueryWrapper<UserCart>()
                        .eq(UserCart::getUserId, userId)
                        .eq(UserCart::getProductId, productId));
        LocalDateTime now = LocalDateTime.now();
        for (UserCart row : rows) {
            row.setQuantity(quantity);
            row.setUpdateTime(now);
            cartMapper.updateById(row);
        }
    }

    @Override
    @Transactional
    public void decreaseQuantity(Long userId, Long productId, Integer quantity) {
        List<UserCart> rows = cartMapper.selectList(
                new LambdaQueryWrapper<UserCart>()
                        .eq(UserCart::getUserId, userId)
                        .eq(UserCart::getProductId, productId));
        if (rows.isEmpty()) {
            return;
        }
        int total = rows.stream().mapToInt(UserCart::getQuantity).sum();
        if (total <= quantity) {
            // 全部删除
            rows.forEach(row -> cartMapper.deleteById(row.getId()));
        } else {
            // 保留第一行,数量置为剩余,删除其他行
            UserCart first = rows.get(0);
            first.setQuantity(total - quantity);
            first.setUpdateTime(LocalDateTime.now());
            cartMapper.updateById(first);
            for (int i = 1; i < rows.size(); i++) {
                cartMapper.deleteById(rows.get(i).getId());
            }
        }
    }

    @Override
    @Transactional
    public void updateSku(Long userId, Long productId, Long oldSkuId, Long newSkuId) {
        UserCart oldRow = findOne(userId, productId, oldSkuId);
        if (oldRow == null) {
            return;
        }
        UserCart newRow = findOne(userId, productId, newSkuId);
        LocalDateTime now = LocalDateTime.now();
        if (newRow != null) {
            // 合并数量到新 SKU 行
            newRow.setQuantity(newRow.getQuantity() + oldRow.getQuantity());
            newRow.setUpdateTime(now);
            cartMapper.updateById(newRow);
            cartMapper.deleteById(oldRow.getId());
        } else {
            oldRow.setSkuId(newSkuId);
            oldRow.setUpdateTime(now);
            cartMapper.updateById(oldRow);
        }
    }

    // ---------- 查询 ----------

    @Override
    public List<UserCart> listByUserId(Long userId) {
        return cartMapper.selectList(
                new LambdaQueryWrapper<UserCart>()
                        .eq(UserCart::getUserId, userId)
                        .orderByDesc(UserCart::getCreateTime));
    }

    @Override
    public List<CartItemVO> listWithProductByUserId(Long userId) {
        List<UserCart> carts = listByUserId(userId);
        if (carts.isEmpty()) {
            return List.of();
        }

        // 收集需要 Feign 的 id 集合
        List<Long> productIds = carts.stream()
                .map(UserCart::getProductId)
                .distinct()
                .collect(Collectors.toList());
        List<Long> skuIds = carts.stream()
                .map(UserCart::getSkuId)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        // 并发调 Feign 太复杂,骨架期同步调即可
        Map<Long, ProductDTO> productMap = fetchProducts(productIds);
        Map<Long, ProductSkuDTO> skuMap = fetchSkus(skuIds);

        List<CartItemVO> result = new ArrayList<>(carts.size());
        for (UserCart cart : carts) {
            CartItemVO vo = CartItemVO.fromCart(cart);
            ProductDTO product = productMap.get(cart.getProductId());
            if (product != null) {
                vo.setProductTitle(product.getTitle());
                vo.setProductImage(product.getImageUrl());
                vo.setBasePrice(product.getBasePrice());
                vo.setProductStatus(product.getStatus());
            }
            if (cart.getSkuId() != null) {
                ProductSkuDTO sku = skuMap.get(cart.getSkuId());
                if (sku != null) {
                    vo.setSkuPrice(sku.getPrice());
                    vo.setStock(sku.getStock());
                    if (sku.getProperties() != null) {
                        String props = sku.getProperties().entrySet().stream()
                                .map(e -> e.getKey() + ": " + e.getValue())
                                .collect(Collectors.joining(" / "));
                        vo.setSkuProperties(props);
                    }
                }
            }
            // 单价:SKU 价 > 商品基础价
            BigDecimal unit = vo.getSkuPrice() != null ? vo.getSkuPrice() : vo.getBasePrice();
            if (unit != null && cart.getQuantity() != null) {
                vo.setTotalPrice(unit.multiply(BigDecimal.valueOf(cart.getQuantity())));
            }
            result.add(vo);
        }
        return result;
    }

    @Override
    public long getCount(Long userId) {
        return cartMapper.selectCount(
                new LambdaQueryWrapper<UserCart>()
                        .eq(UserCart::getUserId, userId));
    }

    // ---------- 内部工具 ----------

    private UserCart findOne(Long userId, Long productId, Long skuId) {
        LambdaQueryWrapper<UserCart> wrapper = new LambdaQueryWrapper<UserCart>()
                .eq(UserCart::getUserId, userId)
                .eq(UserCart::getProductId, productId);
        if (skuId == null) {
            wrapper.isNull(UserCart::getSkuId);
        } else {
            wrapper.eq(UserCart::getSkuId, skuId);
        }
        List<UserCart> rows = cartMapper.selectList(wrapper);
        return rows.isEmpty() ? null : rows.get(0);
    }

    private Map<Long, ProductDTO> fetchProducts(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return Collections.emptyMap();
        }
        try {
            Result<List<ProductDTO>> resp = productClient.batch(ids);
            if (resp != null && resp.isSuccess() && resp.getData() != null) {
                return resp.getData().stream()
                        .collect(Collectors.toMap(ProductDTO::getId, p -> p));
            }
        } catch (Exception e) {
            log.warn("[cart] fetch products via Feign failed: {}", e.getMessage());
        }
        return Collections.emptyMap();
    }

    private Map<Long, ProductSkuDTO> fetchSkus(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return Collections.emptyMap();
        }
        try {
            Result<List<ProductSkuDTO>> resp = productClient.skuBatch(ids);
            if (resp != null && resp.isSuccess() && resp.getData() != null) {
                return resp.getData().stream()
                        .collect(Collectors.toMap(ProductSkuDTO::getId, s -> s));
            }
        } catch (Exception e) {
            log.warn("[cart] fetch skus via Feign failed: {}", e.getMessage());
        }
        return Collections.emptyMap();
    }
}
