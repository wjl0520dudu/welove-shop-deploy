package com.welove.shop.chat.service;

import java.util.List;
import java.util.Map;

public interface AiService {
    /** 同步问答(非流式)。 */
    Map<String, Object> ask(String question, List<Map<String, Object>> context, Long userId, String username);
    /** 异步生成会话标题。 */
    void generateTitle(Long conversationId, String question);

    /**
     * 异步解析文档(调 Python /api/parse)。
     *
     * @param downloadUrl 文件可访问的完整 URL(公共读 OSS / CDN / 本地),ai-service 用 httpx.get 下载
     * @param objectKey   对象存储 key,ai-service 内部去重/缓存用(可空)
     * @param docId       知识库文档 ID
     */
    void parseDocument(String downloadUrl, String objectKey, Long docId);

    /** 异步删除文档的向量索引。 */
    void deleteDoc(Long docId);
}
