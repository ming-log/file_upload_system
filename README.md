# 作业文件上传系统（Homework Upload System）

一个前后端分离的作业文件上传系统。支持**管理员（admin）**、**教师（teacher）**、**学生（student）** 三种角色，覆盖用户管理、班级管理、课程管理、作业管理与作业提交。学生在截止时间前提交符合扩展名与大小限制的文件，文件保存到本地磁盘（可切换 MinIO），提交成功后向学生邮箱发送通知邮件。

- 后端：Python + FastAPI + SQLAlchemy 2.x + Pydantic v2，JWT 鉴权，本地磁盘/MinIO 存储，aiosmtplib 邮件
- 前端：React 18 + TypeScript + Vite + Tailwind + Radix UI（Figma 设计稿实现）
- 数据：默认文件 SQLite（持久化）；默认本地磁盘文件存储（零外部依赖）

---

## 🔑 演示账号

后端启动时会**自动写入一套演示数据**（幂等），可直接登录体验。

| 角色 | 账号 | 密码 | 说明 |
| --- | --- | --- | --- |
| 管理员 admin | `admin` | `admin123` | 启动时自动创建 |
| 教师 teacher | `teacher001` | `teacher123` | 张伟，已绑定一个班级与两门课程 |
| 学生 student | `2022001` / `2022002` / `2022003` | `minglog666` | 用**学号**登录 |

> 设置环境变量 `SEED_DISABLE=1` 可关闭自动播种。`admin123` 等仅供本地开发，生产环境请通过环境变量注入强密码。

### 典型上手流程

1. 用 `admin` / `admin123` 登录 → 管理员视图，可**创建/编辑/删除教师账号**（密码留空默认 `minglog666`）。
2. 用 `teacher001` / `teacher123` 登录 → **创建班级** → **创建课程**（关联班级）→ **创建作业**（关联课程，设置允许文件类型、最大大小、截止时间）→ 在班级内**创建/导入学生**。
3. 用学生学号 + `minglog666` 登录 → **提交作业文件**（支持多文件 + 备注）。

---

## 📁 项目结构

```
file_upload_system/
├── backend/                  # FastAPI 后端（全量 CRUD REST API）
│   ├── app/
│   │   ├── main.py           # 应用工厂 + CORS + 启动播种
│   │   ├── seed.py           # 演示数据播种（幂等）
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

### 2. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

- 应用地址：http://localhost:5173
- 开发环境下 `/api` 请求由 Vite 代理到后端 `http://localhost:8000`（见 `vite.config.ts`）。
  可用环境变量 `VITE_API_TARGET` 覆盖后端地址。

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
| `SEED_DISABLE` | 未设置 | 设为 `1` 关闭启动播种 |
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
