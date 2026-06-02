# 作业文件上传系统 — 后端

基于 **Python + FastAPI + SQLAlchemy 2.x + Pydantic v2** 的后端服务。为对接前端
（Figma 重写版）提供完整的增删改查 REST API。

* 默认数据库：项目内文件 SQLite（`homework.db`），开箱即用、数据持久化。
* 默认文件存储：本地磁盘（`uploaded_files/` 目录），零外部依赖。可经环境变量
  `STORAGE_BACKEND=minio` 切换为 MinIO。
* 已启用 CORS，默认放行本地前端端口（5173 / 3000）。

## 目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 应用工厂（CORS、路由接入、启动播种）
│   ├── seed.py            # 启动时写入演示数据（管理员/教师/学生/班级/课程/作业）
│   ├── models.py          # ORM 模型（角色小写，多文件提交）
│   ├── repository.py      # 全量 CRUD 仓储
│   ├── core/              # 校验纯函数、错误模型
│   ├── services/          # 认证服务（JWT）
│   ├── adapters/          # 存储（本地磁盘 / MinIO）、邮件（SMTP）适配器
│   └── api/               # 路由、依赖注入、序列化、错误映射
└── pyproject.toml
```

## 环境准备

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -e ".[test]"
```

## 运行

```bash
uvicorn app.main:app --reload --port 8000
```

* 健康检查：`GET /health`
* 接口文档：`http://localhost:8000/docs`

启动时自动写入演示数据（幂等）。演示账号：

| 角色   | 账号        | 密码        |
| ------ | ----------- | ----------- |
| 管理员 | `admin`      | `admin123`    |
| 教师   | `teacher001` | `teacher123`  |
| 学生   | `2022001`    | `minglog666`  |

可用环境变量 `SEED_DISABLE=1` 关闭播种。

## 主要 API

| 方法 & 路径                                    | 说明                       | 角色            |
| ---------------------------------------------- | -------------------------- | --------------- |
| `POST /auth/login`                             | 登录，返回 JWT + 用户信息  | 公共            |
| `GET/POST /users`，`PUT/DELETE /users/{id}`    | 用户增删改查               | admin           |
| `POST /users/batch`                            | 批量创建用户               | admin           |
| `GET/POST /classes`，`PUT/DELETE /classes/{id}`| 班级增删改查               | teacher/admin   |
| `GET/POST /classes/{id}/students`              | 班级学生列表/创建          | teacher/admin   |
| `PUT/DELETE /students/{id}`，`GET /students`   | 学生改/删/全量列表         | teacher/admin   |
| `POST /classes/{id}/students/batch`            | 批量导入学生               | teacher         |
| `GET/POST /courses`，`PUT/DELETE /courses/{id}`| 课程增删改查               | teacher/admin   |
| `GET/POST /assignments`，`PUT/DELETE /…/{id}`  | 作业增删改查               | teacher         |
| `GET /submissions`                             | 提交记录（学生仅见自己）   | 全部            |
| `POST /assignments/{id}/submissions`           | 学生上传作业（多文件）     | student         |
| `GET /submissions/{id}/files/{storageId}`      | 下载提交文件               | 全部            |

## 环境变量

| 变量              | 默认值                              | 说明                       |
| ----------------- | ----------------------------------- | -------------------------- |
| `DATABASE_URL`    | `sqlite+pysqlite:///./homework.db`  | 数据库连接串               |
| `STORAGE_BACKEND` | `local`                             | `local` 或 `minio`         |
| `STORAGE_DIR`     | `./uploaded_files`                  | 本地存储目录               |
| `CORS_ORIGINS`    | 本地 5173/3000                      | 允许的前端来源（逗号分隔） |
| `AUTH_SECRET_KEY` | 开发占位值                          | JWT 签名密钥（生产必改）   |

> 注意：`tests/` 下的既有 pytest 套件针对的是旧版后端设计（旧服务类、首字母大写
> 的角色、单文件提交），在本次为对接前端的改造后已不再适用，需重写或移除。
