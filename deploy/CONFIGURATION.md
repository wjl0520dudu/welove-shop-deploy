# 生产配置集中管理

服务器的配置唯一来源是两个文件：

```text
/opt/welove-shop/config/production.env             # 可公开的运行参数
/opt/welove-shop/secrets/production.secrets.env    # 密钥，权限 600
```

对应模板为 `deploy/config/production.env.example` 和 `deploy/secrets/production.secrets.env.example`。GitHub Actions 只读取 SSH 凭据；不会上传或覆盖这两个文件。每次发布只会修改 `config/production.env` 的 `IMAGE_TAG`。

## 配置归属

| 类型 | 位置 | 示例 |
|---|---|---|
| 密钥 | `production.secrets.env` | 数据库密码、JWT、Zilliz token、DashScope key |
| 容器网络/部署参数 | `production.env` | 域名、镜像 tag、`postgres`、`nacos`、`gateway` 地址 |
| AI 检索策略 | `production.env`；稳定后可迁 Nacos | collection、分块、rerank 候选数 |
| Java 动态业务参数 | Nacos（非敏感） | 缓存 TTL、限流、日志级别、功能开关 |
| 前端 API 地址 | 不配置 | 两个 H5 均访问同源 `/api`，由外层 Nginx 转给 Gateway |
| 前端图片域名 | `production.env` | `IMAGE_BASE_URL` 由容器启动时生成公开的 `runtime-config.js` |

Nacos 不能存密码、Token、JWT 或云厂商密钥；这些只放服务器 secrets 文件。修改任一 env 文件后，执行：

```bash
cd /opt/welove-shop
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml up -d
```

## 前端的特殊点

商城与管理端的 API 都是相对路径，因此域名变化无需重建前端镜像。商品图片域名由前端容器启动时生成 `/runtime-config.js`；修改服务器 `IMAGE_BASE_URL` 后执行一次 Compose 更新即可生效，不需要重新构建前端镜像。该文件会被浏览器下载，因此只能包含公开配置，严禁写入 token 或任何密钥。
