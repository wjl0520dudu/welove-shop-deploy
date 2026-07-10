package com.welove.shop.product.exception;

/**
 * product-service 域业务错误码。
 * <p>
 * 编码规则:30xxx = 商品域。
 */
public final class ProductErrorCode {

    private ProductErrorCode() {
    }

    public static final int PRODUCT_NOT_FOUND = 30001;
    public static final int CATEGORY_NOT_FOUND = 30002;
    public static final int SKU_NOT_FOUND = 30003;
    public static final int STOCK_INSUFFICIENT = 30004;
    public static final int PRODUCT_OFF_SHELF = 30005;

    public static final int REVIEW_INVALID_RATING = 30101;
    public static final int REVIEW_CONTENT_EMPTY = 30102;
}
