package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;

@Data
public class FeedbackRequest implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private Long messageId;
    private String feedbackType;
}
