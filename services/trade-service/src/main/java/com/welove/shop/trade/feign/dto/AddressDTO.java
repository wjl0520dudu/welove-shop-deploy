package com.welove.shop.trade.feign.dto;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;

/**
 * Feign 从 user-service 拿地址字段的接收 DTO。
 */
@Data
public class AddressDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long id;
    private Long userId;
    private String receiverName;
    private String phone;
    private String province;
    private String city;
    private String district;
    private String detail;
    private Integer isDefault;
}
