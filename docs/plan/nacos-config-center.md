# Nacos 配置中心接入文档

> **状态**：代码已落地 ✅（2026-07-20，提交 `50d6d23` + `5dbb1d8`）
> **范围**：6 个 Java 微服务（gateway / admin-bff / 4 个 services/*）
> **依赖**：Spring Cloud Alibaba 2023.0.1.2 + Nacos 2.x

---

## 1. 背景

骨架期所有配置都写在 `application.yml` 里（外加本地覆盖 `application-dev.yml`，不进 git）。

进入 Ph2 后，需要：

- 不同环境（dev / staging / prod）的差异配置集中管理
- 配置热更新（不用重启服务）
- 敏感配置（密钥、连接串）统一存放，不进 git
- 跨服务公共配置（JWT、Feign 超时、日志级别）只维护一份

→ 引入 **Nacos 作为配置中心**。

---

## 2. 接入方式：**Modern 风格（Spring Cloud 2023+ 推荐）**

### 2.1 历史包袱（**不用**的方案）

旧 Spring Cloud（≤ 2021.x）要加 `spring-cloud-starter-bootstrap` 才能用 `bootstrap.yml`。

**Spring Cloud 2022.0.x 起**，bootstrap.yml 加载机制被弱化；**Spring Cloud Alibaba 2023 起完全废弃 bootstrap 风格**，改用 **`spring.config.import`** 写法。

> 参考：
> - [SpringCloud2023集成Nacos2.4.3](https://blog.csdn.net/m0_74824483/article/details/145212726)（CSDN）
> - [SCA 官方 Nacos Config 2023 集成指南](https://github.com/alibaba/spring-cloud-alibaba/wiki/Nacos-config)

### 2.2 现代写法（**我们用的**）

不再需要 bootstrap.yml，不再需要 `spring-cloud-starter-bootstrap`，**只在 `application.yml` 里写一行**：

```yaml
spring:
  config:
    import:
      - optional:nacos:nacos-common.yml?group=COMMON_GROUP&refreshEnabled=true
      - optional:nacos:nacos-trade-service.yml?group=TRADE_GROUP&refreshEnabled=true
```

关键点：

| 项 | 值 | 说明 |
|---|---|---|
| `optional:` 前缀 | **必须** | Nacos 连不上时启动不阻塞,降级本地配置 |
| `nacos:` | SCA 注册的 ConfigDataLoader | SCA 2023 自带,无需额外依赖 |
| `?group=` | 默认 `DEFAULT_GROUP` | Nacos 配置所在的 Group |
| `?refreshEnabled=true` | 开启热刷新 | 改 Nacos 推送后服务自动更新 |

### 2.3 为什么不用 bootstrap starter

我们项目基线是 **Spring Cloud 2023.0.1** + **Spring Cloud Alibaba 2023.0.1.2**。

- 调研结论：2023.0.x BOM 中**已无 `spring-cloud-starter-bootstrap`**，强行加会报 "Could not resolve" 错误
- SCA 2023 起自带 `NacosConfigDataLoader`，通过 `spring.config.import` 直接生效
- 这是 SCA 官方推荐的现代接入方式

---

## 3. Nacos 上需要建的配置清单

进入 Nacos 控制台（默认 `http://127.0.0.1:8848/nacos`，账号 `nacos/nacos`），在 **public** namespace 下创建：

### 3.1 共享配置（所有服务共用）

| Data ID | Group | 内容建议 |
|---|---|---|
| `nacos-common.yml` | `COMMON_GROUP` | `jwt:` / `feign:` / `mybatis-plus:` / `logging:` 等跨服务公共项 |

### 3.2 各服务私有配置

| Data ID | Group | 内容建议 |
|---|---|---|
| `nacos-user-service.yml` | `USER_GROUP` | 短信验证码 mock / Redis key / 用户协议开关 |
| `nacos-product-service.yml` | `PRODUCT_GROUP` | 商品缓存 TTL / 热门商品上限 |
| `nacos-trade-service.yml` | `TRADE_GROUP` | 订单超时 / 支付宝 / 支付回调 URL |
| `nacos-chat-service.yml` | `CHAT_GROUP` | SSE 超时 / 上下文窗口 / 上传限制 |
| `nacos-gateway.yml` | `GATEWAY_GROUP` | 路由表 / CORS / Sentinel 限流规则 |
| `nacos-admin-bff.yml` | `ADMIN_GROUP` | Admin 仪表盘 / Feign 聚合配置 |

> **为什么用 Group 分开？** Group 是 Nacos 的租户/环境隔离单位。未来 staging / prod 可以复用同一 Data ID 不同 Group（如 `STAGING_GROUP` / `PROD_GROUP`），切换时只改 `NACOS_GROUP` 环境变量即可。

---

## 4. 文件改动清单（已落地）

| 文件 | 改动 |
|---|---|
| [pom.xml](../../pom.xml) | 父 POM 新增注释说明（不引入 bootstrap starter）|
| 6 个子服务 pom | 仅保留 `spring-cloud-starter-alibaba-nacos-config`，**不加** bootstrap starter |
| 6 个 `application.yml` | 新增 `spring.config.import` + 简化 `spring.cloud.nacos.*` 块 |
| 6 个 `application-dev.yml` | 删除 `spring.cloud.nacos.config.enabled`（modern 模式下不存在的属性）|

### 4.1 application.yml 模板（trade-service）

```yaml
spring:
  application:
    name: trade-service
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}

  # ---------- Nacos 配置中心(Modern 接入,Spring Cloud 2023+) ----------
  # SCA 自带 NacosConfigDataLoader,通过 spring.config.import 加载。
  # optional:nacos: 表示 Nacos 连不上时启动不阻塞,降级本地 application*.yml。
  config:
    import:
      # 共享配置(所有服务共用:JWT / Feign / 日志级别)
      - optional:nacos:nacos-common.yml?group=COMMON_GROUP&refreshEnabled=true
      # 本服务私有配置(支付宝 / 订单超时扫描)
      - optional:nacos:nacos-trade-service.yml?group=TRADE_GROUP&refreshEnabled=true

  cloud:
    nacos:
      # 服务发现
      discovery:
        server-addr: ${NACOS_SERVER_ADDR:127.0.0.1:8848}
        username: ${NACOS_USERNAME:nacos}
        password: ${NACOS_PASSWORD:nacos}
        namespace: ${NACOS_NAMESPACE:public}
        fail-fast: false
      # 配置中心
      config:
        server-addr: ${NACOS_SERVER_ADDR:127.0.0.1:8848}
        username: ${NACOS_USERNAME:nacos}
        password: ${NACOS_PASSWORD:nacos}
        namespace: ${NACOS_NAMESPACE:public}
        file-extension: yaml
        refresh-enabled: true
```

### 4.2 application-dev.yml 模板（trade-service）

```yaml
spring:
  application:
    name: trade-service

  cloud:
    nacos:
      # 本地 Nacos 配置:由 spring.config.import: optional:nacos:... 控制(见 application.yml)
      # 本地没启 Nacos 时,optional: 前缀会自动跳过,Nacos 8848 起不来也不阻塞启动
      discovery:
        server-addr: ${NACOS_SERVER_ADDR:127.0.0.1:8848}
        namespace: ${NACOS_NAMESPACE:public}
        fail-fast: false       # Nacos 8848 起不来时也不阻塞启动
```

**关键点**：dev yml **不需要** `spring.cloud.nacos.config.enabled: false`（这个属性是 bootstrap 时代的，modern 模式下不存在）。关 Nacos config 用 `optional:` 前缀自动实现。

---

## 5. 配置优先级

启动时属性加载顺序（高 → 低）：

```
1. 启动参数 --key=value
2. 环境变量 KEY=VALUE
3. spring.config.import: optional:nacos:nacos-{service}.yml   ← Nacos 远程
4. spring.config.import: optional:nacos:nacos-common.yml      ← Nacos 远程
5. application-{profile}.yml                                  ← 本地 profile
6. application.yml                                             ← 本地默认
```

> **dev 调试**：本地没启 Nacos → 第 3、4 项加载失败但 `optional:` 前缀跳过，降级使用第 5、6 项本地 yml。开发无障碍。
>
> **prod 部署**：Nacos 必须可达（fail-fast=false 只在本地 dev 生效，生产建议去掉）。

---

## 6. 热刷新（@RefreshScope）

Nacos 改了配置后默认会推送到服务。要让具体 Bean 真正热更新，需要在 Bean 上加 `@RefreshScope`：

```java
@RestController
@RequestMapping("/api/admin/config")
@RefreshScope   // 改了 nacos-admin-bff.yml 自动生效,不用重启
public class AdminConfigController {
    @Value("${admin.dashboard.refresh-interval:30}")
    private int refreshInterval;
}
```

**不支持热刷新的**（改了必须重启）：

- `@ConfigurationProperties` 绑定的对象（除非加 `@RefreshScope`）
- `DataSource` / 连接池配置
- `server.port` 等启动期参数
- `spring.cloud.nacos.*` 元配置

---

## 7. 验证结果（已实测）

接入后跑下面 6 项验证：

| 验证项 | 结果 | 证据 |
|---|---|---|
| Maven 编译 | ✅ BUILD SUCCESS | 11/11 模块通过 |
| trade-service 启动 | ✅ 11s 启动成功 | `Started TradeServiceApplication in 11.106 seconds` |
| NacosConfigDataLoader 加载 | ✅ 触发 | `[Nacos Config] config[dataId=nacos-trade-service.yml] is empty` |
| optional 前缀降级 | ✅ 启动不阻塞 | Nacos 没建配置也能跑（is empty 不报错）|
| 服务注册 | ✅ 完成 | `nacos registry, DEFAULT_GROUP trade-service register finished` |
| 热刷新监听 | ✅ 开启 | `NacosContextRefresher: Listening config: nacos-common.yml` |
| gateway 启动 | ✅ 13.9s 启动 | `Started GatewayApplication in 13.926 seconds` |

---

## 8. 常见问题（FAQ）

### Q1：启动报 "Could not resolve spring-cloud-starter-bootstrap:2023.0.1"

**原因**：误加了 bootstrap starter。Spring Cloud 2023.0.x BOM 中已无该 starter。

**解决**：删除 `<artifactId>spring-cloud-starter-bootstrap</artifactId>`，改用 modern 写法（见 §2.2）。

### Q2：启动报 "No spring.config.import property has been defined"

**原因**：application.yml 缺 `spring.config.import: ...` 配置块（或者 application.yml 没被加载，比如 dev yml 覆盖了所有配置）。

**解决**：

1. 检查 application.yml 顶层有 `spring.config.import: [optional:nacos:...]`
2. 检查 application-{profile}.yml 没有把 `spring.config.import` 覆盖掉

### Q3：启动报 "Connection refused: 127.0.0.1:8848"

**原因**：本地 Nacos 没起。

**解决**：

- **dev**：`optional:` 前缀已经避免阻塞，无需处理（会走本地 yml 降级）。
- **prod**：检查 Nacos 部署、`fail-fast` 是否误设 true。

### Q4：Nacos 改了配置不生效

**排查顺序**：

1. Nacos 控制台 → 配置管理 → 配置列表，看修改时间是否更新
2. 服务日志搜 `NacosConfigDataLoader`，看推送消息是否收到
3. Bean 上是否有 `@RefreshScope`？
4. 是否在黑名单字段内（见 §6）？
5. `spring.cloud.nacos.config.refresh-enabled: true`？

### Q5：多环境隔离怎么做？

用 **namespace + group** 组合：

- **namespace**：开发 / 测试 / 生产（强隔离）
- **group**：同一 namespace 下细分（dev / staging / prod）

```bash
# 生产环境启动参数
NACOS_NAMESPACE=prod-namespace \
NACOS_GROUP=PROD_GROUP \
SPRING_PROFILES_ACTIVE=prod \
java -jar trade-service.jar
```

### Q6：敏感配置（密码 / 密钥）怎么管？

**禁止**写进 `application.yml` 或 `nacos-{service}.yml` 后提交。

Nacos 配置：

- 走 `nacos-{service}.yml`（不进 git）+ Nacos 控制台手动维护
- 或走 K8s Secret / ConfigMap 注入到环境变量：`${DB_PASSWORD}`

**支付宝密钥等见** `docs/plan/alipay-sandbox-payment.md` §11。

---

## 9. 提交记录

| 提交 | 说明 |
|---|---|
| `50d6d23` | feat(config): 接入 Nacos 配置中心（6 个 application.yml 改造 + 父 POM 注释 + .gitignore 恢复 application-dev 规则）|
| `5dbb1d8` | fix(gateway): 补全 spring.config.import + spring.profiles.active（gateway 在首次接入时遗漏）|

---

## 10. 提交后状态

```
$ git log --oneline -5
5dbb1d8 fix(gateway): 补全 spring.config.import + spring.profiles.active
50d6d23 feat(config): 接入 Nacos 配置中心(Modern 风格,spring.config.import)
d7391e6 Merge pull request #13 from wjl0520dudu/fix/ai-service-file-dir
```

---

**变更记录**
- 2026-07-20: 6 个微服务全部接入 Modern 风格 Nacos config；删除 bootstrap.yml 与 bootstrap starter 依赖
- 2026-07-20: 修复 gateway 遗漏的 spring.config.import
- 2026-07-21: 重写本文档（基于实测启动日志）