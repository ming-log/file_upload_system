# Docker 镜像打包与服务器部署流程

本文档固化本项目“本机构建镜像 -> 导出 tar -> 上传服务器 -> 服务器加载运行”的流程。

适用场景：

- 服务器不能直接拉取代码或在线构建。
- 本机已经能正常构建并运行最新前后端。
- 需要把当前代码打成 Docker 镜像后离线部署到服务器。

## 1. 本机构建最新镜像

在项目根目录执行：

```bash
docker compose build backend frontend
```

本项目的镜像名称由 `docker-compose.yml` 固定为：

```text
homework-upload-system-backend:local
homework-upload-system-frontend:local
```

如果担心 Docker 缓存导致前端还是旧页面，可以强制无缓存构建：

```bash
docker compose build --no-cache backend frontend
```

## 2. Docker 构建代理

如果本机网络需要代理才能安装依赖，构建前需要设置 Docker 构建代理。

注意：WSL、Docker Desktop 或电脑重启后，Windows 主机在 WSL/Docker 网络里的 IP 可能变化。不要长期复用旧的 `172.x.x.x` 地址；每次构建前建议重新获取一次。

### 2.1 WSL 中构建

如果代理软件在 Windows 上监听 `7890` 端口，在 WSL 中执行：

```bash
WIN_HOST=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf)

export HTTP_PROXY=http://$WIN_HOST:7890
export HTTPS_PROXY=http://$WIN_HOST:7890
export http_proxy=$HTTP_PROXY
export https_proxy=$HTTPS_PROXY
export NO_PROXY=localhost,127.0.0.1,::1
export no_proxy=$NO_PROXY

docker compose build backend frontend
```

如果代理端口不是 `7890`，把命令里的 `7890` 改成实际端口。

如果构建时报类似下面的错误，通常就是代理 IP 已经过期：

```text
proxyconnect tcp: dial tcp 172.x.x.x:7890: connect: connection refused
```

处理方式是重新运行上面的 `WIN_HOST=...` 命令，刷新代理地址后再构建。

### 2.2 不需要代理时

如果当前网络不需要代理，或代理变量配置错了，可以清空代理再构建：

```bash
HTTP_PROXY= HTTPS_PROXY= NO_PROXY= \
http_proxy= https_proxy= no_proxy= \
docker compose build backend frontend
```

### 2.3 PowerShell 中构建

如果在 Windows PowerShell 里执行 Docker 构建，并且代理在 Windows 本机 `7890` 端口，可优先使用 Docker Desktop 支持的主机名：

```powershell
$env:HTTP_PROXY = "http://host.docker.internal:7890"
$env:HTTPS_PROXY = "http://host.docker.internal:7890"
$env:http_proxy = $env:HTTP_PROXY
$env:https_proxy = $env:HTTPS_PROXY
$env:NO_PROXY = "localhost,127.0.0.1,::1"
$env:no_proxy = $env:NO_PROXY

docker compose build backend frontend
```

如果这个地址不可用，改用 WSL 方式获取的 Windows 主机 IP。

## 3. 导出镜像 tar

构建完成后，在本机导出两个镜像：

```bash
docker save -o homework-upload-system-images.tar \
  homework-upload-system-backend:local \
  homework-upload-system-frontend:local
```

建议压缩后再上传：

```bash
gzip -f homework-upload-system-images.tar
```

压缩后文件名为：

```text
homework-upload-system-images.tar.gz
```

可选：生成校验值，上传后用于确认文件没有损坏。

```bash
sha256sum homework-upload-system-images.tar.gz > homework-upload-system-images.tar.gz.sha256
```

## 4. 上传到服务器的文件

把下面文件上传到服务器同一个部署目录，例如 `/opt/homework-upload-system`：

```text
homework-upload-system-images.tar.gz
docker-compose.prod.yml
.env.prod.example
```

建议同时上传：

```text
DEPLOY.md
docs/docker-image-packaging-and-deploy.md
homework-upload-system-images.tar.gz.sha256
```

如果本机已经准备好了真实生产配置，也可以上传 `.env.prod`。注意 `.env.prod` 包含密码和密钥，不要提交到 Git。

## 5. 服务器加载镜像

进入服务器部署目录：

```bash
cd /opt/homework-upload-system
```

如果上传了校验文件，先检查：

```bash
sha256sum -c homework-upload-system-images.tar.gz.sha256
```

加载镜像：

```bash
gunzip -c homework-upload-system-images.tar.gz | docker load
```

确认镜像存在：

```bash
docker images | grep homework-upload-system
```

## 6. 配置生产环境变量

第一次部署时创建 `.env.prod`：

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

必须重点修改：

```env
FRONTEND_PORT=8880
CORS_ORIGINS=http://服务器IP:8880
AUTH_SECRET_KEY=替换为随机长密钥
ADMIN_ACCOUNT=admin
ADMIN_PASSWORD=替换为强密码
ADMIN_EMAIL=管理员邮箱
SMTP_HOST=邮件服务器
SMTP_USERNAME=发件账号
SMTP_PASSWORD=发件密码
SMTP_FROM=发件邮箱
```

生成随机密钥：

```bash
openssl rand -hex 32
```

当前生产 compose 已把前端端口映射为：

```yaml
ports:
  - "${FRONTEND_PORT:-80}:80"
```

因此 `.env.prod` 中设置 `FRONTEND_PORT=8880` 后，访问地址是：

```text
http://服务器IP:8880/
```

## 7. 数据持久化目录

当前生产 compose 已把后端数据映射到服务器本机目录：

```text
./data/backend:/data
```

默认数据位置：

```text
./data/backend/homework.db
./data/backend/uploaded_files
```

不要删除服务器上的 `./data/backend`。否则 SQLite 数据库和本地上传文件都会丢失。

## 8. 启动或更新服务

启动：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
```

查看状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

查看日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f
```

以后更新版本时，重新上传新的 `homework-upload-system-images.tar.gz` 后执行：

```bash
gunzip -c homework-upload-system-images.tar.gz | docker load
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
```

正常更新不需要删除容器数据目录。

## 9. 确认服务器运行的是新前端

如果服务器页面仍然显示旧的“文本批量导入”，先确认服务器容器里的前端静态文件是否包含新的 Excel 导入文案：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec frontend \
  sh -c "grep -R '选择 Excel\|下载示例\|每行一名学生' -n /usr/share/nginx/html | head"
```

判断方式：

```text
出现“选择 Excel”或“下载示例”：新前端镜像已经生效。
出现“每行一名学生”：服务器仍在使用旧前端镜像或旧静态文件。
```

如果还是旧版本，按下面顺序处理：

```bash
gunzip -c homework-upload-system-images.tar.gz | docker load
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
docker compose -f docker-compose.prod.yml --env-file .env.prod exec frontend \
  sh -c "grep -R '选择 Excel\|下载示例\|每行一名学生' -n /usr/share/nginx/html | head"
```

浏览器仍显示旧页面时，再强制刷新浏览器缓存或换无痕窗口访问。

## 10. 常见问题

### 管理员账号登录不上

后端启动脚本只会在“没有管理员账号”时创建 `.env.prod` 里的初始管理员。已有数据库不会因为修改 `.env.prod` 自动重置管理员密码。

如果是新服务器第一次部署，确认 `.env.prod` 中的 `ADMIN_ACCOUNT` 和 `ADMIN_PASSWORD` 是否就是你正在输入的账号密码。

### 端口访问不到

确认 `.env.prod`：

```env
FRONTEND_PORT=8880
CORS_ORIGINS=http://服务器IP:8880
```

确认服务器防火墙、安全组已放行 `8880`。

### 上传或导入 Excel 失败

查看后端日志：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs backend
```

如果前面还有宝塔、Nginx、Caddy、Cloudflare 等反向代理，也需要同步放大上传大小限制。
