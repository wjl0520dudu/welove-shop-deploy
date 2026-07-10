package com.welove.shop.chat.service;

import java.util.List;
import java.util.Map;

public interface AiService {
    /** 同步问答(非流式)。 */
    Map<String, Object> ask(String question, List<Map<String, Object>> context, Long userId, String username);
    /** 异步生成会话标题。 */
    void generateTitle(Long conversationId, String question);
    /** 异步解析文档(调 Python /api/parse)。 */
    void parseDocument(String filePath, Long docId);
    /** 异步删除文档的向量索引。 */
    void deleteDoc(Long docId);
}
