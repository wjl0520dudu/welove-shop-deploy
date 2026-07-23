# 小白发布清单

完成本清单后，今后只要打 Git tag 就会自动部署。

## 第一次：腾讯云服务器

1. 按 `docs/deployment/tencent-cvm-github-actions.md` 的“腾讯云基础初始化”安装 Docker，并创建 `deploy` 用户。
2. 在服务器执行：

```bash
sudo mkdir -p /opt/welove-shop/secrets
sudo chown -R deploy:deploy /opt/welove-shop
```

3. 将 `deploy/production.env.example` 复制为服务器文件：

```bash
cp /opt/welove-shop/release/production.env.example /opt/welove-shop/secrets/production.env
nano /opt/welove-shop/secrets/production.env
chmod 600 /opt/welove-shop/secrets/production.env
```

如果服务器上还没有 `release/production.env.example`，从本地通过 `scp` 上传该文件；只需做一次。

4. 在该文件填写：GitHub 用户/组织名、域名、PostgreSQL/Redis 密码、Zilliz endpoint/token、DashScope/LLM 密钥、JWT 密钥。

## 第二次：GitHub

在仓库 Settings → Environments → New environment 创建 `production`，添加：

```text
SSH_HOST          腾讯云公网 IP
SSH_USER          deploy
SSH_PRIVATE_KEY   GitHub 专用部署私钥
```

然后让服务器登录 GHCR（私有镜像必需）：

```bash
echo '<只含 read:packages 权限的 GitHub PAT>' | docker login ghcr.io -u '<GitHub用户名>' --password-stdin
```

## 第三次：发布

```bash
git tag -a v1.0.0 -m "release: v1.0.0"
git push origin v1.0.0
```

打开 GitHub → Actions → `Release to Tencent CVM`，等待成功。首次发布默认 HTTP；确认服务可用后再按完整部署文档配置域名和 HTTPS。

## 日常发布

只需创建新 tag，例如 `v1.0.1`。不要手动登录服务器拉代码或构建镜像。

## 出错时只看两处

1. GitHub Actions 的失败步骤；
2. 服务器命令：

```bash
cd /opt/welove-shop
docker compose --env-file secrets/production.env -f docker-compose.prod.yml ps
docker compose --env-file secrets/production.env -f docker-compose.prod.yml logs --tail=100 ai-service
```
