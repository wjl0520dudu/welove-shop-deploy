package com.welove.shop.product.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品主表实体。
 */
@Data
@TableName("product")
public class Product implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 商品编码,如 p_beauty_001,全局唯一。 */
    private String productCode;

    /** 所属分类 ID。 */
    private Long categoryId;

    /** 商品标题。 */
    private String title;

    /** 品牌。 */
    private String brand;

    /** 子分类,如 "精华"/"化妆水"。 */
    private String subCategory;

    /** 基础价格。 */
    private BigDecimal basePrice;

    /** 主图 URL(相对路径,前端渲染时拼 CDN)。 */
    private String imageUrl;

    /** 商品描述,长文本,同时作为 RAG 语料。 */
    private String description;

    /** 逗号分隔的标签串。 */
    private String tags;

    /** 综合评分,0-5,BigDecimal(3,2)。 */
    private BigDecimal rating;

    /** 评价总数。 */
    private Integer reviewCount;

    /** 累计销量。 */
    private Integer salesCount;

    /** 1=上架, 0=下架。 */
    private Integer status;

    /** 向量化状态:0=未处理, 1=已生成向量。 */
    private Integer embeddingStatus;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
