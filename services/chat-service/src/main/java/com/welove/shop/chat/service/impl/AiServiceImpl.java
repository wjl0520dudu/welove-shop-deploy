package com.welove.shop.chat.service.impl;

import com.welove.shop.chat.entity.Conversation;
import com.welove.shop.chat.service.AiService;
import com.welove.shop.chat.mapper.ConversationMapper;
import com.welove.shop.chat.mapper.KnowledgeDocMapper;
import com.welove.shop.chat.entity.KnowledgeDoc;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class AiServiceImpl implements AiService {
    private final RestTemplate restTemplate;
    private final ConversationMapper conversationMapper;
    private final KnowledgeDocMapper knowledgeDocMapper;
    @Value("${ai.service.url}") private String aiUrl;

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> ask(String question, List<Map<String, Object>> context, Long userId, String username) {
        Map<String, Object> body = new java.util.HashMap<>();
        body.put("question", question);
        body.put("context", context);
        body.put("user_id", userId);
        body.put("username", username);
        body.put("is_admin", false);
        try {
            Map<String, Object> resp = restTemplate.postForObject(aiUrl + "/assistant/run", body, Map.class);
            return resp != null ? resp : Map.of("answer", "AI 服务暂不可用");
        } catch (Exception e) {
            log.warn("[AiService] /assistant/run failed: {}", e.getMessage());
            return Map.of("answer", "AI 服务暂不可用,请稍后再试");
        }
    }

    @Override @Async
    public void generateTitle(Long conversationId, String question) {
        try {
            Map<String, String> body = Map.of("conversation_id", conversationId.toString(), "question", question);
            Map<String, Object> resp = restTemplate.postForObject(aiUrl + "/summary", body, Map.class);
            if (resp != null && resp.containsKey("title")) {
                Conversation conv = conversationMapper.selectById(conversationId);
                if (conv != null) {
                    conv.setTitle(resp.get("title").toString());
                    conversationMapper.updateById(conv);
                }
            }
        } catch (Exception e) {
            log.warn("[AiService] /summary failed: {}", e.getMessage());
        }
    }

    @Override @Async
    public void parseDocument(String downloadUrl, String objectKey, Long docId) {
        try {
            // 走 ai-service 的 /api/rag/admin/parse 端点,支持 download_url 下载
            Map<String, Object> body = Map.of(
                    "download_url", downloadUrl,
                    "doc_id", docId,
                    "title", "",
                    "doc_type", "md"
            );
            Map<String, Object> resp = restTemplate.postForObject(aiUrl + "/rag/admin/parse", body, Map.class);
            KnowledgeDoc doc = knowledgeDocMapper.selectById(docId);
            if (doc != null) {
                boolean ok = resp != null && "success".equals(resp.get("status"));
                doc.setStatus(ok ? "COMPLETED" : "FAILED");
                if (!ok) doc.setErrorMessage(String.valueOf(resp.getOrDefault("detail", "unknown")));
                knowledgeDocMapper.updateById(doc);
            }
        } catch (Exception e) {
            log.warn("[AiService] /rag/admin/parse failed: {}", e.getMessage());
            KnowledgeDoc doc = knowledgeDocMapper.selectById(docId);
            if (doc != null) { doc.setStatus("FAILED"); doc.setErrorMessage(e.getMessage()); knowledgeDocMapper.updateById(doc); }
        }
    }

    @Override @Async
    public void deleteDoc(Long docId) {
        try {
            restTemplate.postForObject(aiUrl + "/rag/admin/delete", Map.of("doc_id", docId), Map.class);
        } catch (Exception e) { log.warn("[AiService] /rag/admin/delete failed: {}", e.getMessage()); }
    }
}
