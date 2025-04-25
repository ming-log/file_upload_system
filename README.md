# 文件上传系统

一个基于FastAPI和SQLite的文件上传系统，提供了用户管理、班级管理、课程管理和作业提交功能。

## 功能特性

- 多角色支持：管理员、教师、学生
- 班级和课程管理
- 作业发布与提交
- 文件上传与下载
- 用户友好的界面，蓝色调科技感

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic
- 前端：HTML、CSS、JavaScript、Jinja2模板
- 数据库：SQLite

## 项目结构

```
file_upload_system/
├── app/
│   ├── models/           # 数据库模型
│   ├── routers/          # API路由
│   ├── uploads/          # 上传文件存储目录
│   ├── database.py       # 数据库配置
│   ├── auth.py           # 认证逻辑
│   └── schemas.py        # 数据验证模式
├── static/
│   ├── css/              # 样式表
│   └── js/               # JavaScript文件
├── templates/            # HTML模板
├── main.py               # 应用程序入口
└── requirements.txt      # 依赖项
```

## 安装与启动

1. 安装依赖：

```bash
uv venv
uv sync
```

2. 启动应用：

```bash
python main.py
```

3. 访问应用：

打开浏览器，访问 http://localhost:8000

## 默认账号

系统启动时会自动创建一个管理员账号：

- 用户名：admin
- 密码：admin123

## 各角色功能

### 管理员

- 管理所有用户（创建、修改、删除）
- 查看系统统计信息

### 教师

- 创建和管理班级
- 创建和管理课程
- 发布作业
- 查看学生提交情况

### 学生

- 查看所在班级的作业
- 上传和提交作业文件
