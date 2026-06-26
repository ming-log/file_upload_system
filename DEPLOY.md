# 服务器 Docker 部署

本文档适用于把本机已构建好的镜像导出为 tar，再上传到服务器运行。

## 1. 本机构建并导出镜像

先在本机用当前代码重新构建镜像：

```bash
docker compose build backend frontend
```

如果你的本机/WSL 环境有不可用的代理变量，先清空代理再构建：

```bash
HTTP_PROXY= HTTPS_PROXY= NO_PROXY= \
http_proxy= https_proxy= no_proxy= \
docker compose build backend frontend
```

然后导出镜像：

```bash
docker save -o homework-upload-system-images.tar \
  homework-upload-system-backend:local \
  homework-upload-system-frontend:local
```

可选压缩：

```bash
gzip homework-upload-system-images.tar
```

## 2. 上传文件到服务器

至少上传这些文件：

```text
homework-upload-system-images.tar
docker-compose.prod.yml
.env.prod.example
```

如果上传的是压缩包，文件名为 `homework-upload-system-images.tar.gz`。

## 3. 服务器加载镜像

```bash
docker load -i homework-upload-system-images.tar
```

压缩包：

```bash
gunzip -c homework-upload-system-images.tar.gz | docker load
```

确认镜像存在：

```bash
docker images | grep homework-upload-system
```

## 4. 配置生产环境变量

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

必须修改：

- `CORS_ORIGINS`：服务器访问地址，例如 `http://服务器IP` 或 `https://域名`
- `AUTH_SECRET_KEY`：随机长密钥，可用 `openssl rand -hex 32`
- `ADMIN_PASSWORD`：初始管理员强密码
- `ADMIN_EMAIL`：管理员邮箱
- `SMTP_*`：邮箱验证码发送配置

默认使用服务器当前目录下的 `./data/backend` 保存 SQLite 数据库和上传文件。容器内路径仍是 `/data`：

```env
DATABASE_URL=sqlite+pysqlite:////data/homework.db
STORAGE_BACKEND=local
STORAGE_DIR=/data/uploaded_files
```

如果使用 MinIO，把 `STORAGE_BACKEND` 改成 `minio` 并填写 `MINIO_*`。

## 5. 启动

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

查看状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

查看日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f
```

访问：

```text
http://服务器IP/
```

如果 `FRONTEND_PORT` 改成了其他端口，例如 `8080`，则访问：

```text
http://服务器IP:8080/
```

## 6. 更新版本

在本机重新构建镜像并导出 tar，上传服务器后执行：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
docker load -i homework-upload-system-images.tar
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

数据保存在服务器部署目录的 `./data/backend`，正常 `down` / `up` 不会删除它。不要手动删除 `./data/backend`，否则会丢失 SQLite 数据库和本地上传文件。

## 7. 备份数据

备份 SQLite 数据库和本地上传文件：

```bash
tar czf backend-data-$(date +%F).tar.gz -C ./data/backend .
```

恢复前先停服务：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
rm -rf ./data/backend/*
tar xzf backend-data-YYYY-MM-DD.tar.gz -C ./data/backend
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## 8. 常见问题

### 前端能打开，但接口失败

检查容器状态和后端日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
docker compose -f docker-compose.prod.yml --env-file .env.prod logs backend
```

确认 `.env.prod` 里的 `AUTH_SECRET_KEY`、`DATABASE_URL`、`SMTP_*` 没有空值。

### 上传大文件失败

前端 nginx 已设置 `client_max_body_size 600m`。如果服务器前面还有宝塔、Nginx、Caddy、Cloudflare 等反向代理，也需要同步放大上传限制。

### 服务器已有 80 端口服务

修改 `.env.prod`：

```env
FRONTEND_PORT=8080
```

然后重新启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```
