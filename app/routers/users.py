from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os, shutil
from pathlib import Path

from app.database import get_db
from app.models import User
from app.schemas import User as UserSchema, UserCreate, UserUpdate
from app.auth import get_current_user, get_password_hash, admin_required, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin/users", response_class=HTMLResponse, name="admin_panel")
async def admin_panel(
    request: Request,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return templates.TemplateResponse(
        "admin_panel.html",
        {"request": request, "user": current_user, "users": users}
    )

@router.get("/users/create", response_class=HTMLResponse, name="create_user_page")
async def create_user_page(
    request: Request,
    current_user: User = Depends(admin_required)
):
    return templates.TemplateResponse(
        "user_create.html",
        {"request": request, "user": current_user}
    )

@router.post("/users/create", name="create_user")
async def create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    # 检查用户名是否已存在
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建新用户
    hashed_password = get_password_hash(password)
    db_user = User(
        username=username,
        hashed_password=hashed_password,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return RedirectResponse(url="/admin/users", status_code=303)

@router.get("/users/{user_id}/edit", response_class=HTMLResponse, name="edit_user")
async def edit_user_page(
    user_id: int,
    request: Request,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 判断是否是admin账户（保护admin账户）
    is_admin_account = user.username == "admin"
    
    return templates.TemplateResponse(
        "user_edit.html",
        {"request": request, "user": current_user, "edit_user": user, "is_admin_account": is_admin_account}
    )

@router.post("/users/{user_id}/update", name="update_user")
async def update_user(
    user_id: int,
    username: str = Form(...),
    password: str = Form(None),
    role: str = Form(...),
    organization: str = Form(None),
    id_number: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 保护admin账户，防止角色被修改
    if user.username == "admin" and role != "admin":
        raise HTTPException(status_code=400, detail="不能修改admin账户的角色")
    
    # 检查新用户名是否与其他用户重复
    if username != user.username:
        # 如果是admin账户，不允许修改用户名
        if user.username == "admin":
            raise HTTPException(status_code=400, detail="不能修改admin账户的用户名")
            
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = username
    
    # 如果提供了新密码，则更新密码
    if password:
        user.hashed_password = get_password_hash(password)
    
    # 设置角色（对于非admin账户）
    if user.username != "admin":
        user.role = role
    
    # 更新用户资料
    user.organization = organization
    user.id_number = id_number
    user.phone = phone
    user.email = email
    
    db.commit()
    db.refresh(user)
    
    return RedirectResponse(url="/admin/users", status_code=303)

@router.get("/users/{user_id}/delete", name="delete_user")
async def delete_user_page(
    user_id: int,
    request: Request,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    
    # 保护admin账户
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除admin账户")
    
    return templates.TemplateResponse(
        "user_delete_confirm.html",
        {"request": request, "user": current_user, "delete_user": user}
    )

@router.post("/users/{user_id}/delete", name="delete_user_confirm")
async def delete_user_confirm(
    user_id: int,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    
    # 保护admin账户
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="不能删除admin账户")
    
    db.delete(user)
    db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=303)

@router.get("/profile", response_class=HTMLResponse, name="profile")
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "user": current_user}
    )

@router.post("/profile/update", name="update_profile")
async def update_profile(
    request: Request,
    avatar: UploadFile = File(None),
    organization: str = Form(None),
    id_number: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 获取当前用户
    user = db.query(User).filter(User.id == current_user.id).first()
    
    # 更新用户资料
    if organization is not None:
        # 学生用户不能修改工作/学习单位
        if user.role != "student":
            user.organization = organization
    
    if id_number is not None:
        # 学生用户不能修改学号/工号
        if user.role != "student":
            user.id_number = id_number
    
    if phone is not None:
        user.phone = phone
    
    if email is not None:
        user.email = email
    
    # 处理头像上传
    if avatar and avatar.filename:
        # 检查文件类型
        allowed_mime_types = ["image/jpeg", "image/png", "image/gif", "image/jpg"]
        if avatar.content_type not in allowed_mime_types:
            messages = {"danger": "只允许上传JPG, JPEG, PNG或GIF格式的图片"}
            response = templates.TemplateResponse(
                "profile.html",
                {"request": request, "user": current_user, "messages": messages}
            )
            return response
            
        # 检查文件大小限制（1MB）
        contents = await avatar.read()
        await avatar.seek(0)  # 重置文件指针
        
        # 1MB = 1024 * 1024 字节
        if len(contents) > 1024 * 1024:
            # 返回错误提示
            messages = {"danger": "头像文件大小超过1MB限制，请选择较小的图片"}
            response = templates.TemplateResponse(
                "profile.html",
                {"request": request, "user": current_user, "messages": messages}
            )
            return response
            
        # 确保上传目录存在
        avatar_dir = Path("static/uploads/avatars")
        avatar_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置文件名和保存路径
        file_ext = os.path.splitext(avatar.filename)[1]
        avatar_path = f"uploads/avatars/user_{user.id}{file_ext}"
        file_path = f"static/{avatar_path}"
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(contents)  # 使用已读取的内容
        
        # 更新用户头像路径
        user.avatar = avatar_path
    
    db.commit()
    db.refresh(user)
    
    return RedirectResponse(url="/profile", status_code=303)

@router.get("/change-password", response_class=HTMLResponse, name="change_password_page")
async def change_password_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    # 管理员不通过此页面修改密码
    if current_user.role == "admin":
        raise HTTPException(status_code=403, detail="管理员不能通过此页面修改密码")
    
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request, "user": current_user}
    )

@router.post("/change-password", name="change_password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 管理员不通过此页面修改密码
    if current_user.role == "admin":
        raise HTTPException(status_code=403, detail="管理员不能通过此页面修改密码")
    
    # 验证确认密码
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="新密码和确认密码不一致")
    
    # 获取当前用户
    user = db.query(User).filter(User.id == current_user.id).first()
    
    # 验证当前密码
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    
    # 更新密码
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return RedirectResponse(url="/profile", status_code=303) 