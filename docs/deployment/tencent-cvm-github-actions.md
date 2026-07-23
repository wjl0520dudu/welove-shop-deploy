# 腾讯云 CVM：从空服务器到 Tag 自动部署

本文是私有部署资料，不提交当前项目仓库。目标是：腾讯云 CVM 运行 PostgreSQL、Redis、Nacos 和所有应用；Zilliz Cloud 运行 Milvus；推送 Git Tag 后由 GitHub Actions 构建镜像并发布。

## 0. 先理解启动顺序

`docker-compose.prod.yml` 是**整套系统的容器清单**，不是只启动应用的文件。首次上线分三层启动，顺序不可颠倒：

```text
0. 服务器目录 + 配置文件 + Compose/Nginx 文件
1. 基础容器：PostgreSQL、Redis、Nacos
2. 外部依赖：Zilliz 连通并已单独导入向量数据
3. 应用容器：AI、Java 服务、Gateway、前端、Nginx
4. 后续发布：Tag -> Actions 构建镜像 -> 服务器 pull + compose up
```

首次不能直接打 Tag：服务器上还没有密钥文件、Compose 文件、GHCR 登录态和基础数据库。完成本篇第 1～7 节后，才打第一个 Tag。

## 1. 最终服务器文件布局

服务器不需要克隆业务仓库，也不需要 Maven/npm/Python 构建环境。部署目录固定为：

```text
/opt/welove-shop/
├── docker-compose.prod.yml          # Actions 每次发布覆盖，非密钥
├── config/
│   └── production.env                # 非敏感运行参数，Actions 只更新 IMAGE_TAG
├── secrets/
│   └── production.secrets.env        # 密钥，只在服务器保存，绝不提交/上传 Actions
├── nginx/
│   └── default.conf.template         # Actions 每次发布覆盖
├── certbot/
│   ├── conf/                         # HTTPS 证书（后续创建）
│   └── www/                          # ACME 校验文件
└── release/                          # Actions 上传时的临时目录
```

PostgreSQL、Redis、Nacos 的数据不在上述目录，而在 Docker named volume 中：`postgres_data`、`redis_data`、`nacos_data`。不要执行 `docker compose down -v`，否则会删除这些数据。

## 2. 先准备外部账户与安全组

1. 在 Zilliz Cloud 创建集群，保存 HTTPS Endpoint 与 API Token。
2. 准备 DashScope、对象存储、域名等运行期密钥。
3. 腾讯云安全组只开放：22（仅你的 IP；GitHub Actions 需能 SSH）、80、443。
4. 不要开放 5432、6379、8000、8080、8848 或 Milvus 端口到公网。

费用：CVM、云硬盘、快照、带宽按腾讯云账单计费；Zilliz 免费版有容量/请求上限；DashScope 的 LLM、embedding、rerank 按用量消耗。Docker、Compose、GitHub Actions 公共仓库通常免费；私有仓库的 Actions/GHCR 有套餐配额。

## 3. 初始化 CVM（只做一次）

以下按 Ubuntu 22.04/24.04。先用 root 或有 sudo 权限的用户登录。

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
```

重新登录 `deploy` 后验证：

```bash
docker version
docker compose version
```

4C8G 建议建 2GB swap，降低 Java 服务冷启动 OOM 的概率：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
free -h
```

## 4. 在服务器创建目录和运行期密钥（先于 Compose）

以 `deploy` 用户执行：

```bash
sudo mkdir -p /opt/welove-shop/{config,secrets,nginx,certbot/conf,certbot/www,release}
sudo chown -R deploy:deploy /opt/welove-shop
chmod 700 /opt/welove-shop/secrets
```

从本地上传两份模板：一份集中管理非敏感运行参数，另一份保存密钥。

```powershell
# 在本地仓库根目录执行；替换服务器 IP
scp deploy/config/production.env.example deploy@<CVM_IP>:/opt/welove-shop/config/production.env
scp deploy/secrets/production.secrets.env.example deploy@<CVM_IP>:/opt/welove-shop/secrets/production.secrets.env
```

```bash
# 在服务器执行
chmod 600 /opt/welove-shop/secrets/production.secrets.env
nano /opt/welove-shop/config/production.env
nano /opt/welove-shop/secrets/production.secrets.env
```

将域名、镜像仓库、网络地址、检索策略等填写到 `config/production.env`；将密码、Token、API Key 填写到 `secrets/production.secrets.env`。两份模板中都不能保留 `replace-with-...`。关键项如下：

```dotenv
# config/production.env
GHCR_OWNER=你的-github-用户名或组织名（小写）
IMAGE_TAG=bootstrap
SHOP_DOMAIN=你的商城域名
ADMIN_DOMAIN=你的管理端域名
MILVUS_URL=https://Zilliz-Endpoint

# secrets/production.secrets.env
POSTGRES_PASSWORD=随机长密码
REDIS_PASSWORD=随机长密码
MILVUS_TOKEN=Zilliz-API-Token
LLM_API_KEY=LLM-Key
JWT_SECRET=随机 32 位以上密钥
```

密钥文件不提交 Git、不放进 Docker 镜像、不配置到 GitHub Secrets。GitHub Secrets 只保存 SSH 部署凭据。完整变量归属见 `deploy/CONFIGURATION.md`。

## 5. 首次把 Compose 与 Nginx 文件放上服务器

这一步的目的只是让服务器拥有容器编排定义；之后同名文件由 GitHub Actions 自动覆盖。

```powershell
# 在本地仓库根目录执行
scp deploy/docker-compose.prod.yml deploy/nginx.conf.template deploy@<CVM_IP>:/opt/welove-shop/release/
```

```bash
# 在服务器执行
cp /opt/welove-shop/release/docker-compose.prod.yml /opt/welove-shop/docker-compose.prod.yml
cp /opt/welove-shop/release/nginx.conf.template /opt/welove-shop/nginx/default.conf.template
cd /opt/welove-shop
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml config > /dev/null
echo $?  # 必须输出 0
```

最后一条只校验变量与 YAML，不会启动容器。

## 6. 先启动基础容器并确认数据库

Compose 已列出了全部容器，但首次先只启动有状态基础设施：

```bash
cd /opt/welove-shop
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml up -d postgres redis nacos
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml ps
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml logs --tail=80 postgres
```

预期：PostgreSQL 状态为 `healthy`，Redis/Nacos 为 `running`。此时 Docker 已创建 `postgres_data`、`redis_data`、`nacos_data` 持久卷；重启容器不会丢数据。

不要手工创建 `user_svc`、`product_svc` 等 schema。应用第一次启动时由各自 Flyway migration 初始化。若该项目的 migration 尚不完整，应先补齐 migration，再上线，不能依赖手工 SQL。

## 7. 单独验证并初始化 Zilliz

在你的本地开发机（已安装项目 Python 依赖）配置 Zilliz 的 endpoint/token，再运行只读验证：

```powershell
cd ai-service
python scripts/check_milvus_connection.py --remote
```

确认后选择线上知识库 collection，例如：

```dotenv
MILVUS_COLLECTION=knowledge_v21_fixed
RAG_PARENT_CHILD_ENABLED=false
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

首次创建 collection 与导入知识/商品向量必须作为**一次性运维动作**执行；不要放入每次 Tag 发布。完成导入后再次运行检查脚本，确认目标 collection 存在。商品检索 collection 使用 `MILVUS_PRODUCT_COLLECTION=product_mm_collection`，与知识库 collection 独立。

## 8. 配置 GHCR 与 GitHub Actions

服务器需要能拉取 GHCR 私有镜像。创建只含 `read:packages` 的 GitHub PAT 后，在服务器执行：

```bash
echo '<GHCR_READ_TOKEN>' | docker login ghcr.io -u '<GITHUB_USER>' --password-stdin
```

GitHub 仓库设置 `Settings -> Environments -> production`，添加：

```text
SSH_HOST          CVM 公网 IP 或域名
SSH_USER          deploy
SSH_PRIVATE_KEY   专用于 Actions 的私钥
SSH_PORT          22（若未使用默认端口才填写）
```

为 Actions 创建单独 SSH 密钥对，把公钥加入 `/home/deploy/.ssh/authorized_keys`，私钥填入 `SSH_PRIVATE_KEY`。不要使用个人主密钥。

## 9. 第一次完整应用发布

现在才打首个 Tag：

```bash
git tag -a v1.0.0 -m "release: v1.0.0"
git push origin v1.0.0
```

Actions 的实际顺序是：构建并推送所有镜像 -> 上传最新 Compose/Nginx 文件 -> 服务器更新 `IMAGE_TAG` -> `docker compose pull` -> `docker compose up -d --remove-orphans`。

这一次会在已运行的 PostgreSQL、Redis、Nacos 基础上启动：AI 服务、Java 服务、Gateway、前端与 Nginx。Compose 的 `depends_on` 会保证依赖容器先启动；应用如因 Nacos/Flyway 尚未就绪而短暂失败，会按 `restart: unless-stopped` 自动重试。

发布后检查：

```bash
cd /opt/welove-shop
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml ps
docker stats --no-stream
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml logs --tail=100 ai-service
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml logs --tail=100 gateway
```

确认 HTTP 正常后再配置 DNS、Certbot 和 Nginx 443。没有证书前，Compose 只开放 80 是正常设计。

## 10. 日常发布、回滚和禁忌

日常发布只需新 Tag；不需登录服务器拉代码或手工构建。

回滚到已验证版本：

```bash
cd /opt/welove-shop
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=v1.0.0/' config/production.env
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml pull
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml up -d --remove-orphans
```

数据库 migration 不应通过回滚镜像自动回退。采用向前兼容的 migration，并在发布前备份 PostgreSQL：

```bash
docker compose --env-file config/production.env --env-file secrets/production.secrets.env -f docker-compose.prod.yml exec -T postgres pg_dump -U welove_app welove_shop_search > /opt/welove-shop/backup-$(date +%F).sql
```

严禁：提交任一生产 env 文件、在 Actions 日志输出 token、开放数据库/Redis/Nacos 到公网、执行 `docker compose down -v`、或把 Zilliz 全量灌库绑定到每次部署。
