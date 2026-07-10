package com.welove.shop.product.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 商品分类实体(扁平一级,无 parent_id)。
 */
@Data
@TableName("category")
public class Category implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    private String description;

    private String iconUrl;

    /** 排序权重,越小越靠前。 */
    private Integer sortOrder;

    /** 是否启用:1=启用, 0=禁用(与 monolith TINYINT(1) 对齐,不用 Boolean 避免类型转换)。 */
    private Integer isActive;

    private LocalDateTime createTime;
}
