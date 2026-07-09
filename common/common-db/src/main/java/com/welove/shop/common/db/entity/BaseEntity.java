package com.welove.shop.common.db.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.TableField;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 通用实体基类。
 * <p>
 * 提供 create_time / update_time 两个字段,配合 {@code AutoFillMetaObjectHandler} 自动填充:
 * <ul>
 *   <li>insert 时:同时填 create_time 和 update_time</li>
 *   <li>update 时:只填 update_time</li>
 * </ul>
 * 不需要自动填充的表可以不继承本类(直接自己维护)。
 * <p>
 * 主键 id 交给各实体自己声明(策略可能不同:自增/雪花/UUID),不放到基类。
 */
public class BaseEntity implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableField(value = "create_time", fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(value = "update_time", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    public LocalDateTime getCreateTime() {
        return createTime;
    }

    public void setCreateTime(LocalDateTime createTime) {
        this.createTime = createTime;
    }

    public LocalDateTime getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(LocalDateTime updateTime) {
        this.updateTime = updateTime;
    }
}
