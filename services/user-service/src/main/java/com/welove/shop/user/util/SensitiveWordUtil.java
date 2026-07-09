package com.welove.shop.user.util;

import cn.hutool.dfa.WordTree;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.List;

/**
 * 敏感词检测工具。
 * <p>
 * 用 Hutool DFA WordTree 做多模式匹配,主要用于用户名注册/更新的合规校验。
 * 词表目前硬编码,后续可迁到配置中心或独立管理接口。
 */
@Component
public class SensitiveWordUtil {

    private final WordTree wordTree = new WordTree();

    @PostConstruct
    void init() {
        List<String> defaults = Arrays.asList("暴力", "色情", "赌博", "admin", "root", "system");
        wordTree.addWords(defaults);
    }

    /** 判断给定文本是否包含任意敏感词;null 视为不包含。 */
    public boolean contains(String text) {
        if (text == null) {
            return false;
        }
        return wordTree.isMatch(text);
    }

    /**
     * 将文本中命中的所有敏感词替换为等长星号,不改变整体长度。
     */
    public String filter(String text) {
        if (text == null) {
            return null;
        }
        return wordTree.matchAll(text).stream()
                .distinct()
                .reduce(text, (acc, word) -> acc.replace(word, "*".repeat(word.length())));
    }
}
