package com.welove.shop.common.db.handler;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import org.apache.ibatis.reflection.MetaObject;

import java.time.LocalDateTime;

/**
 * 自动填充 create_time / update_time。
 * <p>
 * 与 {@code BaseEntity} 上的 {@code @TableField(fill = ...)} 注解配合工作:
 * <ul>
 *   <li>insert 前:两个字段都塞成 now()</li>
 *   <li>update 前:只塞 update_time</li>
 * </ul>
 * 只有实体字段是 null 时才填,已手动设过值的不覆盖。
 */
public class AutoFillMetaObjectHandler implements MetaObjectHandler {

    @Override
    public void insertFill(MetaObject metaObject) {
        LocalDateTime now = LocalDateTime.now();
        strictInsertFill(metaObject, "createTime", LocalDateTime.class, now);
        strictInsertFill(metaObject, "updateTime", LocalDateTime.class, now);
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        strictUpdateFill(metaObject, "updateTime", LocalDateTime.class, LocalDateTime.now());
    }
}
