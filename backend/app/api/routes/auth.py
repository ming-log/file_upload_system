"""认证路由（公共端点，无需令牌）。

* ``GET /auth/captcha``：生成图形验证码，返回 ``captchaId`` 与可直接用于
  ``<img>`` 的 ``image`` data URL。
* ``POST /auth/login``：校验账号/密码（及验证码）并在成功时签发 JWT，同时返回
  当前登录用户的完整信息（含角色、姓名、邮箱，以及学生的 ``classId``），供前端
  直接构造会话用户。

验证码规则：学生（``student``）登录必须提供并通过验证码校验；其他角色（演示用的
管理员/教师）若提供了验证码也会校验，未提供则放行，便于演示账号快速登录。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import (
    get_auth_service,
    get_captcha_service,
    get_repository,
    utcnow,
)
from app.api.errors import http_exception_for
from app.core.errors import ErrorCode
from app.repository import Repository
from app.services.auth_service import AuthService
from app.services.captcha_service import CaptchaService

__all__ = ["router"]

router = APIRouter(prefix="/auth", tags=["auth"])


class CaptchaResponse(BaseModel):
    captchaId: str = Field(..., description="验证码标识，登录时回传")
    image: str = Field(..., description="验证码图片（SVG data URL）")


class LoginRequest(BaseModel):
    account: str = Field(..., description="登录账号或学号")
    password: str = Field(..., description="登录密码")
    captchaId: Optional[str] = Field(default=None, description="验证码标识（GET /auth/captcha 返回）")
    captcha: Optional[str] = Field(default=None, description="用户输入的验证码")


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


@router.get("/captcha", response_model=CaptchaResponse, summary="获取登录验证码")
def get_captcha(
    captcha_service: CaptchaService = Depends(get_captcha_service),
) -> CaptchaResponse:
    captcha_id, image = captcha_service.generate()
    return CaptchaResponse(captchaId=captcha_id, image=image)


@router.post("/login", response_model=LoginResponse, summary="用户登录")
def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    repository: Repository = Depends(get_repository),
    captcha_service: CaptchaService = Depends(get_captcha_service),
    now: datetime = Depends(utcnow),
) -> LoginResponse:
    # 验证码校验：先确定登录账号对应的用户角色，学生必须通过验证码。
    user = repository.get_user_by_account(body.account)
    is_student = user is not None and user.role == "student"
    # 学生强制校验；其他角色仅在前端传了 captchaId 时校验（演示账号可不传）。
    if is_student or body.captchaId:
        if not captcha_service.verify(body.captchaId, body.captcha, now=now.timestamp()):
            raise http_exception_for(ErrorCode.INVALID_CAPTCHA)

    result = auth_service.login(body.account, body.password, now)
    if not result.ok:
        assert result.error_code is not None
        raise http_exception_for(result.error_code)

    assert result.token is not None
    auth_user = _auth_user(repository, body.account)
    assert auth_user is not None  # 登录成功必能查到用户
    return LoginResponse(access_token=result.token, token_type="bearer", user=auth_user)
