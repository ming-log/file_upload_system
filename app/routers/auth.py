from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate
from app.auth import (
    authenticate_user, create_access_token, get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse, name="login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_for_access_token(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "用户名或密码错误"},
            status_code=400
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # 设置cookie
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
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