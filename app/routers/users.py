from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import User as UserSchema, UserCreate, UserUpdate
from app.auth import get_current_user, get_password_hash, admin_required

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