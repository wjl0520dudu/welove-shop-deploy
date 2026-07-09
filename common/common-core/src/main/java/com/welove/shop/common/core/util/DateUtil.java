package com.welove.shop.common.core.util;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Date;

/**
 * 日期工具类。
 * <p>
 * 只暴露最常用的 LocalDateTime / LocalDate 与 String 的互转,以及 Date 与 LocalDateTime 互转。
 * 复杂日期运算(加减、区间、日历)直接用 hutool 的 DateUtil 或 java.time API,不再自造轮子。
 * <p>
 * 默认时区:系统默认(与 Docker 容器 TZ 保持一致,通常 Asia/Shanghai)。
 */
public final class DateUtil {

    public static final String YMD = "yyyy-MM-dd";
    public static final String YMD_HMS = "yyyy-MM-dd HH:mm:ss";

    private static final DateTimeFormatter FMT_YMD = DateTimeFormatter.ofPattern(YMD);
    private static final DateTimeFormatter FMT_YMD_HMS = DateTimeFormatter.ofPattern(YMD_HMS);

    private DateUtil() {
    }

    // ---------- LocalDateTime ↔ String ----------

    /** LocalDateTime 转 "yyyy-MM-dd HH:mm:ss"。 */
    public static String format(LocalDateTime dateTime) {
        return dateTime == null ? null : dateTime.format(FMT_YMD_HMS);
    }

    /** LocalDateTime 转指定 pattern 字符串。 */
    public static String format(LocalDateTime dateTime, String pattern) {
        if (dateTime == null || pattern == null) {
            return null;
        }
        return dateTime.format(DateTimeFormatter.ofPattern(pattern));
    }

    /** "yyyy-MM-dd HH:mm:ss" 字符串转 LocalDateTime。 */
    public static LocalDateTime parseDateTime(String text) {
        return (text == null || text.isEmpty()) ? null : LocalDateTime.parse(text, FMT_YMD_HMS);
    }

    // ---------- LocalDate ↔ String ----------

    /** LocalDate 转 "yyyy-MM-dd"。 */
    public static String format(LocalDate date) {
        return date == null ? null : date.format(FMT_YMD);
    }

    /** "yyyy-MM-dd" 字符串转 LocalDate。 */
    public static LocalDate parseDate(String text) {
        return (text == null || text.isEmpty()) ? null : LocalDate.parse(text, FMT_YMD);
    }

    // ---------- Date ↔ LocalDateTime(兼容旧 API 场景) ----------

    /** {@link Date} 转 LocalDateTime。 */
    public static LocalDateTime toLocalDateTime(Date date) {
        return date == null ? null
                : date.toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime();
    }

    /** LocalDateTime 转 {@link Date}。 */
    public static Date toDate(LocalDateTime dateTime) {
        return dateTime == null ? null
                : Date.from(dateTime.atZone(ZoneId.systemDefault()).toInstant());
    }
}
