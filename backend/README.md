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
| `GET /auth/captcha`                            | 获取登录验证码             | 公共            |
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
| `GET /submissions/{id}/file?storageId=…`       | 下载提交文件               | 全部（学生仅自己）|
| `GET /assignments/{id}/submissions/export`     | 导出作业全部提交（ZIP）    | teacher/admin   |
| `GET /courses/{id}/submissions/export`         | 导出课程全部提交（ZIP）    | teacher/admin   |

## 环境变量

敏感配置（MinIO / SMTP 凭据）集中在 `backend/.env`（已被 `.gitignore` 忽略），
应用启动时自动加载（见 `app/config.py`）。模板见 `.env.example`，复制为 `.env`
后填写真实值即可。真实环境变量优先于 `.env`，便于在容器/CI 中覆盖。

| 变量                       | 默认值                              | 说明                              |
| -------------------------- | ----------------------------------- | --------------------------------- |
| `DATABASE_URL`             | `sqlite+pysqlite:///./homework.db`  | 数据库连接串                      |
| `STORAGE_BACKEND`          | `local`                             | `local`（本地磁盘）或 `minio`     |
| `STORAGE_DIR`              | `./uploaded_files`                  | 本地存储目录                      |
| `MINIO_ENDPOINT`           | `localhost:9000`                    | MinIO 地址，可带 `http(s)://`     |
| `MINIO_REGION`             | 空                                  | 区域（部分部署需要，如 `us-east-1`）|
| `MINIO_ACCESS_KEY`         | `minioadmin`                        | MinIO Access Key                  |
| `MINIO_SECRET_KEY`         | `minioadmin`                        | MinIO Secret Key                  |
| `MINIO_BUCKET`             | `homework`                          | 存储桶名称                        |
| `SMTP_HOST`                | `localhost`                         | SMTP 主机                         |
| `SMTP_PORT`                | `25`                                | SMTP 端口（465 隐式 TLS / 587 STARTTLS） |
| `SMTP_USERNAME`            | 空                                  | SMTP 用户名                       |
| `SMTP_PASSWORD`            | 空                                  | SMTP 密码                         |
| `SMTP_FROM`                | `no-reply@...local`                 | 发件人地址                        |
| `SMTP_TLS`                 | `auto`                              | `auto`/`ssl`/`starttls`/`none`    |
| `SMTP_ALLOW_INVALID_CERTS` | `false`                             | `true` 时跳过证书校验             |
| `CORS_ORIGINS`             | 本地 5173/3000                      | 允许的前端来源（逗号分隔）        |
| `AUTH_SECRET_KEY`          | 开发占位值                          | JWT 签名密钥（生产必改）          |

## 登录验证码

`GET /auth/captcha` 返回 `{ captchaId, image }`（`image` 为 SVG data URL）。
登录时回传 `captchaId` 与用户输入的 `captcha`。**学生登录必须通过验证码校验**；
演示用的管理员/教师账号若未提供验证码则放行（便于快速登录）。验证码一次性使用、
5 分钟过期、不区分大小写。

## 邮件通知

学生提交或修改作业后，系统通过 SMTP 主动向学生邮箱发送通知（异步执行，发送失败
不影响提交结果）。用户/学生的**邮箱为必填项**。

## 文件存储组织与提交导出

提交文件在对象存储中按 **课程 / 作业 / 学号_姓名** 分层组织（对象键形如
`Web前端开发/React实践/2022001_李明/<uuid>-report.pdf`），不再堆在桶根目录。

* 下载单个提交文件：`GET /submissions/{id}/file?storageId=<对象键>`
  （`storageId` 含 `/`，作为路径段会被路由切断，故经查询参数传递）。学生仅能
  下载自己的提交文件；教师/管理员可下载任意文件。
* 按作业一键导出：`GET /assignments/{id}/submissions/export`
* 按课程一键导出：`GET /courses/{id}/submissions/export`

导出返回 ZIP，按作业导出的结构为：

```
<作业标题>/
  提交状态表.csv          # 该作业所属班级每名学生的提交状态/时间/迟交/文件/备注
  <学号_姓名>/
    <提交文件...>
```

提交状态表为带 BOM 的 UTF-8 CSV，Excel 可直接打开。前端在「作业管理」表格每行
及提交记录弹窗中提供「下载全部提交」按钮；学生在「我的作业」中可下载自己已提交
的最新文件。

> 注意：`tests/` 下的既有 pytest 套件针对的是旧版后端设计（旧服务类、首字母大写
> 的角色、单文件提交），在本次为对接前端的改造后已不再适用，需重写或移除。
