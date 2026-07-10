package com.welove.shop.trade.exception;

/**
 * trade-service 域业务错误码(40xxx)。
 */
public final class TradeErrorCode {

    private TradeErrorCode() {
    }

    // ---------- 购物车 ----------
    public static final int CART_ITEM_NOT_FOUND = 40001;
    public static final int CART_EMPTY = 40002;

    // ---------- 订单 ----------
    public static final int ORDER_NOT_FOUND = 40101;
    public static final int ORDER_STATUS_INVALID = 40102;
    public static final int ORDER_CANNOT_CANCEL = 40103;
    public static final int ORDER_CANNOT_DELETE = 40104;
    public static final int ORDER_ITEMS_EMPTY = 40105;

    // ---------- 跨服务 ----------
    public static final int PRODUCT_NOT_FOUND_REMOTE = 40201;
    public static final int PRODUCT_OFF_SHELF = 40202;
    public static final int SKU_NOT_FOUND_REMOTE = 40203;
    public static final int ADDRESS_NOT_FOUND_REMOTE = 40204;
}
