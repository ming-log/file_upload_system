# 作业文件上传系统 — 后端

基于 **Python + FastAPI + SQLAlchemy 2.x + Pydantic v2** 的后端服务。为对接前端
（Figma 重写版）提供完整的增删改查 REST API。

* 默认数据库：项目内文件 SQLite（`homework.db`），开箱即用、数据持久化。
* 默认文件存储：本地磁盘（`uploaded_files/` 目录），零外部依赖。可经环境变量
  `STORAGE_BACKEND=minio` 切换为 MinIO。
* 已启用 CORS，默认放行本地前端端口（5173 / 3000）。
* **时间统一为北京时间**（Asia/Shanghai, UTC+8）：所有业务时间（创建时间、截止
  时间、提交时间，以及邮件/CSV/序列化输出）均以北京墙钟时间存储与展示，由
  `app/core/clock.py` 统一提供，避免"存 UTC、显示本地"导致的 8 小时偏差。

## 目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 应用工厂（CORS、路由接入）
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

## 创建初始管理员

系统不会自动播种任何账号，全新数据库需先创建一个管理员账号才能登录：

```bash
# 交互式输入密码（推荐，密码不会进入命令行历史）
python -m app.create_admin --account admin --email admin@example.com

# 或通过环境变量提供密码
set ADMIN_PASSWORD=<强密码> && python -m app.create_admin --account admin
```

该命令幂等：若目标账号或任意管理员已存在则跳过。登录后即可在管理端创建教师、班级、课程与学生。

## 主要 API

| 方法 & 路径                                    | 说明                       | 角色            |
| ---------------------------------------------- | -------------------------- | --------------- |
| `GET /auth/schools`                            | 学校列表（学生登录下拉）   | 公共            |
| `GET /auth/captcha`                            | 获取登录验证码             | 公共            |
| `POST /auth/login/student`                     | 学生登录（校+学号+码）     | 公共            |
| `POST /auth/login/teacher`                     | 教师/管理员登录            | 公共            |
| `POST /auth/email/send-code`                   | 发送邮箱验证码             | 已登录          |
| `POST /auth/email/verify`                      | 验证邮箱并改密             | 已登录          |
| `GET /me`，`PUT /me`                            | 查看/更新个人基本信息      | 全部（本人）    |
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

## 登录与邮箱验证

登录分两类：

* **学生登录**（默认）：`POST /auth/login/student`，提交 `school`（下拉，取自
  `GET /auth/schools` 的已建班级学校去重）+ `studentId` + `password` + 图形验证码
  （`captchaId`/`captcha`）。**学号仅在同一学校内唯一**，不同学校可重复，故需配合
  学校定位学生。
* **教师/管理员登录**：`POST /auth/login/teacher`，账号 + 密码，**无需验证码**。
  管理员也走此入口（前端显示「教师登录」）。

`GET /auth/captcha` 返回 `{ captchaId, image }`（SVG data URL）。验证码一次性、
5 分钟过期、不区分大小写。

**学生与教师首次登录强制邮箱验证 + 改密**（管理员豁免）：登录返回的用户信息含
`emailVerified`。为 `false` 时前端引导其完成：

* `POST /auth/email/send-code`（需令牌）：向学生邮箱发送 6 位验证码（10 分钟有效）。
* `POST /auth/email/verify`（需令牌）：提交 `code` + `newPassword`，校验通过后标记
  邮箱已验证并修改密码，方可进入系统。

> JWT 主体（`sub`）使用全局唯一的 `user.id`（学生账号即学号已不再全局唯一）。

## 个人中心

* `GET /me` / `PUT /me`：当前登录用户查看与更新自己的基本信息。
  * **可改**：头像 `avatar`（base64 data URL）、电子邮箱 `email`；姓名 `name` 仅
    教师/管理员可改。
  * **不可改**：学号、姓名（学生）、学校、班级——由学校统一维护，仅展示。
  * 修改邮箱会重置 `emailVerified`（需重新验证）。
* 修改密码：任意用户均可通过「邮箱验证码 + 新密码」修改，复用
  `POST /auth/email/send-code` 与 `POST /auth/email/verify`。
  前端入口在侧边栏底部「个人中心」。

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
