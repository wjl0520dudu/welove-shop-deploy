package com.welove.shop.user.service;

import com.welove.shop.user.entity.Address;

import java.util.List;

/**
 * 收货地址服务。
 */
public interface AddressService {

    List<Address> listByUserId(Long userId);

    Address addAddress(Address address);

    Address updateAddress(Address address);

    void deleteAddress(Long id, Long userId);

    void setDefault(Long id, Long userId);

    /** 按 ID 查地址(不校验归属,供服务间 Feign 调用)。 */
    Address getById(Long id);
}
