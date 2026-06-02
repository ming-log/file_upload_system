"""认证路由（公共端点，无需令牌）。

``POST /auth/login``：校验账号/密码并在成功时签发 JWT，同时返回当前登录用户的
完整信息（含角色、姓名、邮箱，以及学生的 ``classId``），供前端直接构造会话用户。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_auth_service, get_repository, utcnow
from app.api.errors import http_exception_for
from app.repository import Repository
from app.services.auth_service import AuthService

__all__ = ["router"]

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    account: str = Field(..., description="登录账号或学号")
    password: str = Field(..., description="登录密码")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT 会话令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: dict[str, Any] = Field(..., description="当前登录用户信息")


def _auth_user(repo: Repository, account: str) -> Optional[dict[str, Any]]:
    user = repo.get_user_by_account(account)
    if user is None:
        return None
    auth: dict[str, Any] = {
        "id": user.id,
        "role": user.role,
        "account": user.account,
        "name": user.name or "",
        "email": user.email or "",
    }
    if user.role == "student":
        auth["classId"] = user.class_id or ""
    return auth


@router.post("/login", response_model=LoginResponse, summary="用户登录")
def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    repository: Repository = Depends(get_repository),
    now: datetime = Depends(utcnow),
) -> LoginResponse:
    result = auth_service.login(body.account, body.password, now)
    if not result.ok:
        assert result.error_code is not None
        raise http_exception_for(result.error_code)

    assert result.token is not None
    user = _auth_user(repository, body.account)
    assert user is not None  # 登录成功必能查到用户
    return LoginResponse(access_token=result.token, token_type="bearer", user=user)
