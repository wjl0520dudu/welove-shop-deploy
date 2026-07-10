package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

@Data
public class StreamChatRequest implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private Long userId;
    private Long conversationId;
    private String content;
    private String username;
    private boolean isAdmin;
    private String gender;
    private String skinType;
    private List<String> preferenceTags;
}
