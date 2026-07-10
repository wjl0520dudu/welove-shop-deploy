package com.welove.shop.chat.service;

import com.welove.shop.chat.entity.KnowledgeDoc;
import java.util.List;

public interface KnowledgeService {
    KnowledgeDoc uploadDoc(String fileName, String filePath, Long categoryId, String docType);
    List<KnowledgeDoc> listDocs(Long categoryId);
    void deleteDoc(Long docId);
}
