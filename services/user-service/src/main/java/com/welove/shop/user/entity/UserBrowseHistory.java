package com.welove.shop.user.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品浏览历史实体。
 * <p>
 * 同一用户 + 商品的浏览记录去重,保留最新一条(在 Service 里做,数据库不加唯一约束)。
 * <p>
 * productName/productImage/productPrice 三个字段为跨服务展示字段,{@code @TableField(exist=false)}
 * 不映射到数据库。骨架期不填(product-service 尚未落地),后续通过 Feign 补齐。
 */
@Data
@TableName("user_browse_history")
public class UserBrowseHistory implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long productId;

    /** 浏览来源:推荐 / 搜索 / 详情页 等,前端上报。 */
    private String source;

    /** 停留时长(秒),前端上报。 */
    private Integer durationSec;

    private LocalDateTime createTime;

    // ---------- 非数据库字段:Product 冗余展示 ----------
    /** TODO Ph 后续 Feign 调 product-service 填充。 */
    @TableField(exist = false)
    private String productName;

    /** TODO Ph 后续 Feign 调 product-service 填充。 */
    @TableField(exist = false)
    private String productImage;

    /** TODO Ph 后续 Feign 调 product-service 填充。 */
    @TableField(exist = false)
    private BigDecimal productPrice;
}
