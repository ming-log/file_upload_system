from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate
from app.auth import (
    authenticate_user, create_access_token, get_password_hash, get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES, verify_password
)
from app.templates import templates

router = APIRouter()

@router.get("/login", response_class=HTMLResponse, name="login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_for_access_token(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # 添加调试日志
    print(f"尝试登录用户: {username}")
    
    user = authenticate_user(db, username, password)
    if not user:
        print(f"用户验证失败: {username}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "用户名或密码错误"},
            status_code=400
        )
    
    print(f"用户验证成功: {username}, 角色: {user.role}")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    print(f"已为用户 {username} 创建Token")
    
    # 重定向URL取决于用户状态
    redirect_url = "/dashboard"
    if user.first_login == 1 or password == "123456":
        print(f"用户需要修改密码: {username}")
        redirect_url = "/change-password"
    
    # 创建响应并设置cookie
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    
    print(f"已设置Cookie，重定向到: {redirect_url}")
    
    return response

# 注册功能暂时关闭，只允许管理员和教师导入学生
# @router.post("/register", response_model=Any)
# def register(
#     request: Request,
#     username: str = Form(...),
#     password: str = Form(...),
#     role: str = Form(...),
#     db: Session = Depends(get_db)
# ):
#     # 检查用户名是否已存在
#     db_user = db.query(User).filter(User.username == username).first()
#     if db_user:
#         return templates.TemplateResponse(
#             "login.html",
#             {"request": request, "error": "用户名已存在"},
#             status_code=400
#         )
#     
#     # 创建新用户
#     hashed_password = get_password_hash(password)
#     db_user = User(
#         username=username,
#         hashed_password=hashed_password,
#         role=role
#     )
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     
#     # 注册成功后重定向到登录页
#     response = RedirectResponse(url="/login", status_code=303)
#     return response

@router.get("/logout", name="logout")
def logout(response: Response):
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response 

@router.get("/change-password", response_class=HTMLResponse, name="change_password")
async def change_password_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """显示密码修改页面"""
    return templates.TemplateResponse(
        "change_password.html", 
        {"request": request, "user": current_user}
    )

@router.post("/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    response: Response,
    current_password: str = Form(...),  # 添加当前密码字段
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    phone: str = Form(None),
    email: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """处理密码修改请求"""
    # 验证当前密码
    if not verify_password(current_password, current_user.hashed_password):
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": current_user, "error": "当前密码不正确"},
            status_code=400
        )
    
    # 验证新密码和确认密码是否匹配
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": current_user, "error": "新密码和确认密码不匹配"},
            status_code=400
        )
    
    # 验证新密码不是"123456"
    if new_password == "123456":
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "user": current_user, "error": "新密码不能为默认密码(123456)"},
            status_code=400
        )
    
    # 更新用户密码和个人信息
    user = db.query(User).filter(User.id == current_user.id).first()
    user.hashed_password = get_password_hash(new_password)
    user.first_login = 0  # 标记为非首次登录
    
    # 更新其他可选字段
    if phone:
        user.phone = phone
    if email:
        user.email = email
    
    db.commit()
    
    # 返回到仪表盘，提示密码修改成功
    response = RedirectResponse(url="/dashboard?password_changed=1", status_code=303)
    return response 