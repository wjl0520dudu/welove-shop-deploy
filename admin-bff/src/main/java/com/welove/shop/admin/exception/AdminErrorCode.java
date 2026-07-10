package com.welove.shop.admin.exception;

public final class AdminErrorCode {
    private AdminErrorCode() {}
    public static final int INVALID_CREDENTIALS = 60001;
    public static final int ADMIN_NOT_FOUND     = 60002;
    public static final int NOT_ADMIN_TOKEN     = 60003;
}
