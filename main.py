import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
import json
from datetime import datetime

from app.database import engine, get_db, Base
from app.models import User
from app.routers import auth, users, classes, courses, assignments, dashboard
from app.auth import get_current_user
from app.templates import templates

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 创建上传目录
os.makedirs("app/uploads", exist_ok=True)

# 定义lifespan上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在应用启动时执行的代码
    db = next(get_db())
    try:
        print("检查和创建管理员账户...")
        # 检查是否已存在admin用户名
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            from app.auth import get_password_hash
            # 创建默认管理员账号
            admin_password = "admin123"
            hashed_password = get_password_hash(admin_password)
            print(f"创建管理员账户，密码哈希: {hashed_password[:20]}...")
            
            admin_user = User(
                username="admin",
                hashed_password=hashed_password,
                role="admin",
                first_login=0  # 设置为非首次登录，避免密码修改循环
            )
            db.add(admin_user)
            db.commit()
            print("已创建默认管理员账号，用户名: admin，密码: admin123")
        else:
            # 始终重设管理员密码以确保可以登录
            from app.auth import get_password_hash, verify_password
            admin_password = "admin123"
            
            # 生成新密码
            new_hashed_password = get_password_hash(admin_password)
            print(f"更新管理员密码: {new_hashed_password[:20]}...")
            
            # 更新管理员信息
            admin.hashed_password = new_hashed_password
            admin.first_login = 0  # 设置为非首次登录
            db.commit()
            print("已更新管理员密码: admin123")
    except Exception as e:
        db.rollback()
        print(f"创建/更新管理员账号时出错: {str(e)}")
    
    yield  # 这里是应用运行的地方
    
    # 在应用关闭时执行的代码（如果有的话）

# 创建FastAPI应用
app = FastAPI(title="文件上传系统", lifespan=lifespan)

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

# 全局异常处理
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    处理HTTP异常，返回美化的错误页面
    """
    status_code = exc.status_code
    detail = str(exc.detail)
    
    # 根据状态码设置错误信息
    if status_code == 404:
        message = "找不到您请求的页面"
    elif status_code == 403:
        message = "您没有权限访问此资源"
    elif status_code == 401:
        message = "请先登录后再访问此页面"
    elif status_code == 400:
        message = "请求参数有误"
    else:
        message = "发生了错误"
    
    # 检查是否是AJAX请求
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail, "message": message}
        )
    
    # 获取返回URL
    referer = request.headers.get("referer", "/")
    back_url = referer if referer else "/"
    
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": status_code,
            "message": message,
            "detail": detail,
            "back_url": back_url,
            "user": getattr(request.state, "user", None)
        }, 
        status_code=status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理表单验证错误
    """
    # 格式化验证错误
    error_details = ""
    for error in exc.errors():
        field = ".".join(error["loc"])
        message = error["msg"]
        error_details += f"字段 '{field}': {message}\n"
    
    # 检查是否是AJAX请求
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JSONResponse(
            status_code=422,
            content={"detail": error_details, "message": "表单验证失败"}
        )
    
    # 获取返回URL
    referer = request.headers.get("referer", "/")
    back_url = referer if referer else "/"
    
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 422,
            "message": "表单验证失败",
            "detail": error_details,
            "back_url": back_url,
            "user": getattr(request.state, "user", None)
        }, 
        status_code=422
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    处理所有其他未捕获的异常
    """
    # 记录错误日志
    print(f"未处理的异常: {type(exc).__name__}: {str(exc)}")
    
    # 检查是否是AJAX请求
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "message": "服务器内部错误"}
        )
    
    # 获取返回URL
    referer = request.headers.get("referer", "/")
    back_url = referer if referer else "/"
    
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 500,
            "message": "服务器内部错误",
            "detail": f"{type(exc).__name__}: {str(exc)}",
            "back_url": back_url,
            "user": getattr(request.state, "user", None)
        }, 
        status_code=500
    )

# 包含路由
app.include_router(auth.router, tags=["认证"])
app.include_router(users.router, prefix="/admin", tags=["用户管理"])
app.include_router(classes.router, tags=["班级管理"])
app.include_router(courses.router, tags=["课程管理"])
app.include_router(assignments.router, tags=["作业管理"])
app.include_router(dashboard.router, tags=["仪表盘"])

# 根路由重定向到登录页面或仪表盘
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # 检查用户是否已登录
    # 在cookie中查找access_token
    try:
        token = request.cookies.get("access_token")
        print(f"首页获取到cookie: {token and token[:15]}...")
        
        if token:
            try:
                if token.startswith("Bearer "):
                    token = token[7:]  # 去掉"Bearer "前缀
                
                # 直接验证令牌
                from jose import jwt
                from app.auth import SECRET_KEY, ALGORITHM
                from app.database import get_db
                
                # 解码令牌并验证
                print(f"首页尝试验证令牌: {token[:10]}...")
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                username = payload.get("sub")
                
                print(f"首页验证令牌成功，用户: {username}")
                
                if username:
                    # 在数据库中查找用户
                    db = next(get_db())
                    from app.models import User
                    user = db.query(User).filter(User.username == username).first()
                    
                    if user:
                        print(f"首页找到用户: {username}, 重定向到仪表盘")
                        # 用户已登录，重定向到仪表盘
                        return RedirectResponse(url="/dashboard")
                    else:
                        print(f"首页未在数据库中找到用户: {username}")
            except Exception as e:
                # 令牌无效，继续重定向到登录页面
                print(f"首页令牌验证失败: {str(e)}")
    except Exception as e:
        print(f"首页处理时发生未知错误: {str(e)}")
    
    print("用户未登录，重定向到登录页面")
    # 用户未登录，重定向到登录页面
    return RedirectResponse(url="/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
