package com.welove.shop.product.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

/**
 * AI 商品推荐日志实体(供离线分析 + 推荐算法迭代)。
 * <p>
 * recommendedProductIds 存 JSONB List&lt;Long&gt;,MyBatis-Plus JacksonTypeHandler 处理。
 */
@Data
@TableName(value = "recommendation_log", autoResultMap = true)
public class RecommendationLog implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 推荐给谁(可空,支持匿名推荐)。 */
    private Long userId;

    /** 触发推荐的会话 id。 */
    private String sessionId;

    /** 触发推荐的消息 id(跨服务字段,不加 FK)。 */
    private Long messageId;

    /** 用户原始 query。 */
    private String query;

    /** 识别到的意图。 */
    private String intent;

    /** 推荐商品 id 列表,JSONB 列。 */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<Long> recommendedProductIds;

    /** 推荐理由(给用户看的)。 */
    private String recommendReason;

    /** Agent 完整推理过程(内部用)。 */
    private String agentReasoning;

    /** 1=点击, 0=未点击。 */
    private Integer userClicked;

    /** 用户反馈:1=满意, 0=不满意, null=未反馈。 */
    private Integer userFeedback;

    private LocalDateTime createTime;
}
