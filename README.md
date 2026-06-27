# 作业文件上传系统（Homework Upload System）

一个前后端分离的作业文件上传系统。支持**管理员（admin）**、**教师（teacher）**、**学生（student）** 三种角色，覆盖用户管理、班级管理、课程管理、作业管理与作业提交。学生在截止时间前提交符合扩展名与大小限制的文件，文件保存到本地磁盘（可切换 MinIO），提交成功后向学生邮箱发送通知邮件。

- 后端：Python + FastAPI + SQLAlchemy 2.x + Pydantic v2，JWT 鉴权，本地磁盘/MinIO 存储，aiosmtplib 邮件
- 前端：React 18 + TypeScript + Vite + Tailwind + Radix UI（Figma 设计稿实现）
- 数据：默认文件 SQLite（持久化）；默认本地磁盘文件存储（零外部依赖）

---

## 📁 项目结构

```
file_upload_system/
├── backend/                  # FastAPI 后端（全量 CRUD REST API）
│   ├── app/
│   │   ├── main.py           # 应用工厂 + CORS
│   │   ├── create_admin.py   # 创建初始管理员的 CLI（幂等）
│   │   ├── models.py         # ORM 模型（角色小写，多文件提交）
│   │   ├── repository.py     # 全量 CRUD 仓储 + 级联删除
│   │   ├── core/             # validators(纯函数) / errors
│   │   ├── services/         # auth_service(JWT)
│   │   ├── adapters/         # storage(本地磁盘/MinIO) / email(SMTP)
│   │   └── api/              # deps / serializers / errors / routes/
│   └── pyproject.toml
├── frontend/                 # React + Vite SPA（Figma 实现）
│   ├── src/app/
│   │   ├── api.ts            # 后端 API 客户端（fetch + JWT）
│   │   ├── context.tsx       # 全局状态：调用 API 加载/写入数据
│   │   ├── types.ts          # 数据类型
│   │   └── components/       # 登录 / 布局 / 管理员·教师·学生页面
│   ├── vite.config.ts        # /api 代理到后端
│   └── package.json
├── docs/
│   └── docker-image-packaging-and-deploy.md # 镜像打包、导出与服务器部署
├── docker-compose.yml        # 本地开发/测试 Docker Compose
├── docker-compose.prod.yml   # 服务器生产 Docker Compose
├── .env.prod.example         # 生产环境变量模板
├── DEPLOY.md                 # 服务器部署说明
└── .kiro/specs/homework-upload-system/   # 需求 / 设计 / 任务文档
```

---

## 🚀 快速开始

### 环境要求

- Python ≥ 3.11
- Node.js ≥ 18（建议 20+）；前端使用 **pnpm**

### 1. 启动后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e ".[test]"
python -m uvicorn app.main:app --reload --port 8000
```

- API 服务：http://localhost:8000
- 交互式文档（Swagger）：http://localhost:8000/docs

> 首次部署需创建一个初始管理员账号（系统不再自动播种任何账号）：
>
> ```bash
> # 交互式输入密码（推荐）
> python -m app.create_admin --account admin --email admin@example.com
> ```
>
> 该命令幂等；登录后即可在管理端创建教师、班级、课程与学生。

### 2. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

- 应用地址：http://localhost:5173
- 开发环境下 `/api` 请求由 Vite 代理到后端 `http://localhost:8000`（见 `vite.config.ts`）。
  可用环境变量 `VITE_API_TARGET` 覆盖后端地址。

### 3. 使用 Docker Compose 启动

```bash
docker compose up --build
```

- 前端：http://localhost:5173
- 后端：http://localhost:8000
- Swagger：http://localhost:8000/docs

容器默认使用 Docker volume `backend_data` 持久化 SQLite 数据库与上传文件。全新
volume 不包含任何演示账号，首次使用需进入后端容器创建管理员：

```bash
docker compose exec backend python -m app.create_admin --account admin --email admin@example.com
```

### 4. 生产 Docker 部署

生产部署推荐先在本机构建最新镜像，导出为 tar 包，再上传服务器运行。详细流程见：

- `DEPLOY.md`
- `docs/docker-image-packaging-and-deploy.md`

本机构建镜像：

```bash
docker compose build backend frontend
```

如果在 WSL 中构建且需要使用 Windows 本机代理，代理 IP 可能会随 WSL/Docker 网络变化。每次构建前建议重新获取默认网关：

```bash
WSL_GATEWAY=$(ip route | awk '/default/ {print $3; exit}')

export HTTP_PROXY=http://$WSL_GATEWAY:7890
export HTTPS_PROXY=http://$WSL_GATEWAY:7890
export http_proxy=$HTTP_PROXY
export https_proxy=$HTTPS_PROXY
export NO_PROXY=localhost,127.0.0.1,::1
export no_proxy=$NO_PROXY

docker compose build backend frontend
```

导出镜像：

```bash
docker save -o homework-upload-system-images.tar \
  homework-upload-system-backend:local \
  homework-upload-system-frontend:local
gzip -f homework-upload-system-images.tar
```

服务器至少上传：

```text
homework-upload-system-images.tar.gz
docker-compose.prod.yml
.env.prod.example
```

服务器加载并启动：

```bash
gunzip -c homework-upload-system-images.tar.gz | docker load
cp .env.prod.example .env.prod
# 编辑 .env.prod：FRONTEND_PORT、CORS_ORIGINS、AUTH_SECRET_KEY、ADMIN_*、SMTP_* 等
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
```

生产 compose 默认将前端容器 `80` 端口映射到 `.env.prod` 中的 `FRONTEND_PORT`，当前模板默认：

```env
FRONTEND_PORT=8880
```

因此默认访问：

```text
http://服务器IP:8880/
```

后端数据默认持久化到服务器部署目录：

```text
./data/backend/homework.db
./data/backend/uploaded_files
```

不要删除 `./data/backend`，否则会丢失 SQLite 数据库和本地上传文件。

---

## ⚙️ 配置（环境变量）

### 后端

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+pysqlite:///./homework.db` | 数据库连接串 |
| `STORAGE_BACKEND` | `local` | `local`（本地磁盘）或 `minio` |
| `STORAGE_DIR` | `./uploaded_files` | 本地存储目录 |
| `CORS_ORIGINS` | 本地 5173/3000 | 允许的前端来源（逗号分隔） |
| `AUTH_SECRET_KEY` | 开发占位值 | JWT 签名密钥（生产必改） |
| `MINIO_*` / `SMTP_*` | 见 `backend/README.md` | 仅在切换 MinIO / 真实邮件时需要 |

### 前端

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_API_TARGET` | `http://localhost:8000` | dev server `/api` 代理目标 |

---

## 🧱 关键业务规则

- **登录**：JWT 有效期 30 分钟，令牌含角色声明；空密码用户禁止密码登录。登录成功返回完整用户信息。
- **角色门控**：用户管理需 admin；班级/课程/作业、学生增删改需 teacher；作业提交需 student。
- **级联删除**：删除班级会一并清理其学生、课程、作业及提交；删除课程清理其作业与提交；删除作业清理其提交。
- **作业约束**：允许的文件类型由教师自定义（前端提供常见类型与 `*` 任意类型）；最大文件大小由滑块设置。
- **提交校验**：角色 → 作业存在 → 截止时间 → 非空文件 → 扩展名（不区分大小写）→ 大小 → 保存到存储 → 创建/覆盖记录 → 异步邮件通知（失败不影响提交）。
- **重复提交**：同一学生对同一作业再次提交会覆盖既有记录。
- **批量创建/导入**：逐条校验，失败记录跳过并返回明细（行号/学号 + 原因）与计数。

---

## ⚠️ 说明

- 默认文件 SQLite 与本地磁盘存储开箱即用，无需安装 MinIO/SMTP。
- 用户密码以明文存储与比较（符合本项目规格）；生产化应引入密码哈希。
- `backend/tests/` 下的既有 pytest 套件针对旧版后端设计（旧服务类、首字母大写角色、单文件提交），在本次为对接前端的改造后已不再适用，需要重写或移除后才能运行。
