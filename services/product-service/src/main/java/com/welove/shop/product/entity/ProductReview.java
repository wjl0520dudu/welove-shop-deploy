package com.welove.shop.product.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 商品评价实体。
 */
@Data
@TableName("product_review")
public class ProductReview implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long productId;

    /** 评价用户 ID(可空,支持外部导入无用户绑定的评价)。 */
    private Long userId;

    /** 展示昵称,匿名时前端显示 "匿名用户"。 */
    private String nickname;

    /** 1-5 星。 */
    private Integer rating;

    private String content;

    /** 1=匿名, 0=非匿名。 */
    private Integer isAnonymous;

    private LocalDateTime createTime;
}
