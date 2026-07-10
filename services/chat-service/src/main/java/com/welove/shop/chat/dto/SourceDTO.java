package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;

@Data
public class SourceDTO implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private String source;
    private String docId;
    private String docName;
    private Integer page;
}
