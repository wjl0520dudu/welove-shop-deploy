package com.welove.shop.common.core.util;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.util.List;

/**
 * JSON 工具类。
 * <p>
 * 基于 Jackson,统一配置:
 * <ul>
 *   <li>忽略 null 字段(NON_NULL)</li>
 *   <li>反序列化时未知字段不抛异常(FAIL_ON_UNKNOWN_PROPERTIES=false)</li>
 *   <li>日期不用时间戳(WRITE_DATES_AS_TIMESTAMPS=false)</li>
 *   <li>启用 JSR-310(LocalDate / LocalDateTime / Duration 等 java.time 支持)</li>
 * </ul>
 * ObjectMapper 线程安全,内部单例复用。
 */
public final class JsonUtil {

    private static final ObjectMapper MAPPER = JsonMapper.builder()
            .addModule(new JavaTimeModule())
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false)
            .serializationInclusion(JsonInclude.Include.NON_NULL)
            .build();

    private JsonUtil() {
    }

    /** 直接暴露 ObjectMapper,给需要更细控制的场景用。 */
    public static ObjectMapper getMapper() {
        return MAPPER;
    }

    /** 对象转 JSON 字符串。 */
    public static String toJson(Object obj) {
        if (obj == null) {
            return null;
        }
        try {
            return MAPPER.writeValueAsString(obj);
        } catch (Exception e) {
            throw new IllegalStateException("Jackson serialize failed: " + e.getMessage(), e);
        }
    }

    /** JSON 字符串转对象。 */
    public static <T> T fromJson(String json, Class<T> clazz) {
        if (json == null || json.isEmpty()) {
            return null;
        }
        try {
            return MAPPER.readValue(json, clazz);
        } catch (Exception e) {
            throw new IllegalStateException("Jackson deserialize failed: " + e.getMessage(), e);
        }
    }

    /**
     * JSON 字符串转泛型对象(List/Map/嵌套泛型)。
     * <pre>
     *   List&lt;User&gt; users = JsonUtil.fromJson(json, new TypeReference&lt;List&lt;User&gt;&gt;() {});
     * </pre>
     */
    public static <T> T fromJson(String json, TypeReference<T> typeReference) {
        if (json == null || json.isEmpty()) {
            return null;
        }
        try {
            return MAPPER.readValue(json, typeReference);
        } catch (Exception e) {
            throw new IllegalStateException("Jackson deserialize failed: " + e.getMessage(), e);
        }
    }

    /** JSON 字符串直接转 List<T>,内部拼装 CollectionType,免写 TypeReference。 */
    public static <T> List<T> toList(String json, Class<T> elementType) {
        if (json == null || json.isEmpty()) {
            return null;
        }
        try {
            return MAPPER.readValue(json,
                    MAPPER.getTypeFactory().constructCollectionType(List.class, elementType));
        } catch (Exception e) {
            throw new IllegalStateException("Jackson deserialize list failed: " + e.getMessage(), e);
        }
    }
}
