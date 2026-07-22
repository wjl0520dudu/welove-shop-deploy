package com.welove.shop.chat.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("knowledge_doc")
public class KnowledgeDoc implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    @TableId(type = IdType.AUTO) private Long id;
    private String docName;
    /** 对外可访问的完整 URL(公共读 OSS / CDN / 本地);兼容历史可能是相对路径。 */
    private String filePath;
    /** 对象存储内部的 key(OSS / 本地磁盘统一),用于删除/查重;新增字段,旧数据为 NULL。 */
    private String objectKey;
    private Long categoryId;
    private String docType;
    private String status;
    private String errorMessage;
    private LocalDateTime createTime;
}
