package com.welove.shop.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.welove.shop.user.entity.Address;
import com.welove.shop.user.mapper.AddressMapper;
import com.welove.shop.user.service.AddressService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class AddressServiceImpl implements AddressService {

    private final AddressMapper addressMapper;

    @Override
    public List<Address> listByUserId(Long userId) {
        return addressMapper.selectList(
                new LambdaQueryWrapper<Address>()
                        .eq(Address::getUserId, userId)
                        .orderByDesc(Address::getIsDefault)
                        .orderByDesc(Address::getCreateTime));
    }

    @Override
    @Transactional
    public Address addAddress(Address address) {
        if (address.getIsDefault() != null && address.getIsDefault() == 1) {
            clearDefault(address.getUserId());
        }
        LocalDateTime now = LocalDateTime.now();
        address.setCreateTime(now);
        address.setUpdateTime(now);
        addressMapper.insert(address);
        return address;
    }

    @Override
    @Transactional
    public Address updateAddress(Address address) {
        if (address.getIsDefault() != null && address.getIsDefault() == 1) {
            clearDefault(address.getUserId());
        }
        address.setUpdateTime(LocalDateTime.now());
        addressMapper.updateById(address);
        return address;
    }

    @Override
    @Transactional
    public void deleteAddress(Long id, Long userId) {
        addressMapper.delete(
                new LambdaQueryWrapper<Address>()
                        .eq(Address::getId, id)
                        .eq(Address::getUserId, userId));
    }

    @Override
    @Transactional
    public void setDefault(Long id, Long userId) {
        clearDefault(userId);
        Address address = new Address();
        address.setId(id);
        address.setIsDefault(1);
        address.setUpdateTime(LocalDateTime.now());
        addressMapper.updateById(address);
    }

    /** 清掉某用户所有已标记为默认的地址(不真正删,只是 is_default=0)。 */
    private void clearDefault(Long userId) {
        Address update = new Address();
        update.setIsDefault(0);
        update.setUpdateTime(LocalDateTime.now());
        addressMapper.update(update,
                new LambdaUpdateWrapper<Address>()
                        .eq(Address::getUserId, userId)
                        .eq(Address::getIsDefault, 1));
    }

    @Override
    public Address getById(Long id) {
        return addressMapper.selectById(id);
    }
}
