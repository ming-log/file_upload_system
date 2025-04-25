import os
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, get_db, Base
from app.models import User
from app.routers import auth, users, classes, courses, assignments, dashboard
from app.auth import get_current_user

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 创建上传目录
os.makedirs("app/uploads", exist_ok=True)

# 创建FastAPI应用
app = FastAPI(title="文件上传系统")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2模板
templates = Jinja2Templates(directory="templates")

# 包含路由
app.include_router(auth.router, tags=["认证"])
app.include_router(users.router, tags=["用户管理"])
app.include_router(classes.router, tags=["班级管理"])
app.include_router(courses.router, tags=["课程管理"])
app.include_router(assignments.router, tags=["作业管理"])
app.include_router(dashboard.router, tags=["仪表盘"])

# 根路由重定向到登录页面
@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")

# 初始化管理员账号
@app.on_event("startup")
async def startup_event():
    db = next(get_db())
    try:
        # 检查是否已存在admin用户名
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            from app.auth import get_password_hash
            # 检查是否已有其他管理员
            any_admin = db.query(User).filter(User.role == "admin").first()
            if not any_admin:
                # 创建默认管理员账号
                admin_user = User(
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    role="admin"
                )
                db.add(admin_user)
                db.commit()
                print("已创建默认管理员账号，用户名: admin，密码: admin123")
            else:
                print("已存在管理员账号，跳过创建默认管理员")
        else:
            print("admin用户名已存在，跳过创建默认管理员")
    except Exception as e:
        db.rollback()
        print(f"创建管理员账号时出错: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
