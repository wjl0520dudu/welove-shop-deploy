package com.welove.shop.common.security.config;

import com.welove.shop.common.security.jwt.JwtUtil;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

import io.jsonwebtoken.Jwts;

/**
 * common-security 自动装配入口。
 * <p>
 * 装配:
 * <ul>
 *   <li>{@link JwtProperties} — 从 yml 读 jwt.* 配置</li>
 *   <li>{@link JwtUtil} — token 签发/解析工具 Bean(仅当 jwt.secret 配置存在时生效)</li>
 *   <li>{@link PasswordEncoder} — BCrypt 编码器</li>
 * </ul>
 * <p>
 * <b>JwtInterceptor 不在此配置</b>:各服务自己写 WebMvcConfigurer 决定要不要用、白名单、拦截路径,
 * common 不代管。common-security 只提供工具 Bean。
 */
@AutoConfiguration
@EnableConfigurationProperties(JwtProperties.class)
@ConditionalOnClass(Jwts.class)
public class CommonSecurityAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnProperty(prefix = "jwt", name = "secret")
    JwtUtil jwtUtil(JwtProperties props) {
        return new JwtUtil(props);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnClass(BCryptPasswordEncoder.class)
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
