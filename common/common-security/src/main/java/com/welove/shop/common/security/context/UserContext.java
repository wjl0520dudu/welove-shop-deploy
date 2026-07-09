package com.welove.shop.common.security.context;

/**
 * 用户上下文,ThreadLocal 存放当前请求的用户身份。
 * <p>
 * 由 {@code JwtInterceptor} 在请求进入 Controller 前 set,Controller 里通过 {@link #getUserId()} 读。
 * 拦截器在 {@code afterCompletion} 时必须 {@link #clear()},避免线程复用时脏数据。
 */
public final class UserContext {

    private static final ThreadLocal<UserPrincipal> HOLDER = new ThreadLocal<>();

    private UserContext() {
    }

    public static void set(UserPrincipal principal) {
        HOLDER.set(principal);
    }

    public static UserPrincipal get() {
        return HOLDER.get();
    }

    /** 便捷方法:取当前请求的 userId,未登录返回 null。 */
    public static Long getUserId() {
        UserPrincipal p = HOLDER.get();
        return p == null ? null : p.getUserId();
    }

    /** 便捷方法:取当前请求的 userId,未登录抛 IllegalStateException(Controller 明确要求已登录时用)。 */
    public static Long requireUserId() {
        Long id = getUserId();
        if (id == null) {
            throw new IllegalStateException("no user in context, are you behind JwtInterceptor?");
        }
        return id;
    }

    public static void clear() {
        HOLDER.remove();
    }

    /** 当前请求的用户身份不可变载体。 */
    public static class UserPrincipal {

        private final Long userId;
        private final String username;
        private final String phone;
        private final String role;

        public UserPrincipal(Long userId, String username, String phone, String role) {
            this.userId = userId;
            this.username = username;
            this.phone = phone;
            this.role = role;
        }

        public Long getUserId() {
            return userId;
        }

        public String getUsername() {
            return username;
        }

        public String getPhone() {
            return phone;
        }

        public String getRole() {
            return role;
        }
    }
}
