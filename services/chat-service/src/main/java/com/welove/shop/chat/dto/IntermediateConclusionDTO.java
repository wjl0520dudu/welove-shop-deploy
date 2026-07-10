package com.welove.shop.chat.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

@Data
public class IntermediateConclusionDTO implements Serializable {
    @Serial private static final long serialVersionUID = 1L;
    private String stepId;
    private String conclusionType;
    private Object content;
    private Double confidence;
    private List<SourceDTO> sources;
}
