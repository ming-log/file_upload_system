"""认证路由（公共端点，无需令牌）。

登录分两类：

* **学生登录**（默认）：选择学校（取自已建班级去重）+ 学号 + 密码 + 图形验证码。
  学号仅在同校内唯一，故需配合学校定位。学生**首次登录后必须完成邮箱验证并修改
  密码**（``GET /auth/login`` 返回 ``emailVerified=false`` 时，前端引导其走验证流程）。
* **教师登录**（管理员也走此入口，界面显示「教师登录」）：账号 + 密码，**无需验证码**。

邮箱验证与改密流程（学生）：
* ``POST /auth/email/send-code``：已认证学生请求向其邮箱发送 6 位验证码。
* ``POST /auth/email/verify``：提交验证码 + 新密码，校验通过后标记邮箱已验证并改密。

辅助：
* ``GET /auth/schools``：返回已建班级去重的学校列表（学生登录下拉用）。
* ``GET /auth/captcha``：生成图形验证码（学生登录用）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import (
    CurrentUser,
    get_auth_service,
    get_captcha_service,
    get_current_user,
    get_email_service,
    get_email_verification_service,
    get_repository,
    now_provider,
)
from app.api.errors import http_exception_for
from app.core.errors import ErrorCode
from app.core.validators import validate_email, validate_required
from app.repository import Repository
from app.services.auth_service import AuthService
from app.services.captcha_service import CaptchaService
from app.services.email_verification_service import EmailVerificationService

__all__ = ["router"]

router = APIRouter(prefix="/auth", tags=["auth"])


# --------------------------------------------------------------------------- #
# 请求/响应模型                                                                 #
# --------------------------------------------------------------------------- #


class CaptchaResponse(BaseModel):
    captchaId: str = Field(..., description="验证码标识，登录时回传")
    image: str = Field(..., description="验证码图片（SVG data URL）")


class StudentLoginRequest(BaseModel):
    school: str = Field(..., description="所在学校（下拉选择）")
    studentId: str = Field(..., description="学号")
    password: str = Field(..., description="登录密码")
    captchaId: Optional[str] = Field(default=None, description="验证码标识")
    captcha: Optional[str] = Field(default=None, description="用户输入的验证码")


class TeacherLoginRequest(BaseModel):
    account: str = Field(..., description="教师/管理员账号")
    password: str = Field(..., description="登录密码")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT 会话令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: dict[str, Any] = Field(..., description="当前登录用户信息")


class SendCodeResponse(BaseModel):
    status: str = Field(default="ok")
    email: str = Field(..., description="验证码发送到的邮箱（脱敏）")


class VerifyEmailRequest(BaseModel):
    code: str = Field(..., description="邮箱验证码")
    newPassword: str = Field(..., description="新密码")


# --------------------------------------------------------------------------- #
# 辅助                                                                          #
# --------------------------------------------------------------------------- #


def _auth_user(repo: Repository, user_id: str) -> Optional[dict[str, Any]]:
    user = repo.get_user(user_id)
    if user is None:
        return None
    auth: dict[str, Any] = {
        "id": user.id,
        "role": user.role,
        "account": user.account,
        "name": user.name or "",
        "email": user.email or "",
        "emailVerified": bool(user.email_verified),
    }
    if user.role == "student":
        auth["classId"] = user.class_id or ""
        clazz = repo.get_class(user.class_id) if user.class_id else None
        auth["school"] = clazz.school if clazz is not None else ""
    return auth


def _mask_email(email: str) -> str:
    """对邮箱做轻度脱敏：保留首字符与域名，其余以 * 替代。"""
    local, _, domain = email.partition("@")
    if not domain:
        return email
    head = local[0] if local else ""
    return f"{head}***@{domain}"


# --------------------------------------------------------------------------- #
# 公共端点                                                                      #
# --------------------------------------------------------------------------- #


@router.get("/schools", summary="学校列表（学生登录下拉）")
def list_schools(
    repository: Repository = Depends(get_repository),
) -> list[str]:
    return repository.list_schools()


@router.get("/captcha", response_model=CaptchaResponse, summary="获取登录验证码")
def get_captcha(
    captcha_service: CaptchaService = Depends(get_captcha_service),
) -> CaptchaResponse:
    captcha_id, image = captcha_service.generate()
    return CaptchaResponse(captchaId=captcha_id, image=image)


@router.post("/login/student", response_model=LoginResponse, summary="学生登录")
def login_student(
    body: StudentLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    repository: Repository = Depends(get_repository),
    captcha_service: CaptchaService = Depends(get_captcha_service),
    now: datetime = Depends(now_provider),
) -> LoginResponse:
    # 学生登录强制图形验证码。
    if not captcha_service.verify(body.captchaId, body.captcha, now=now.timestamp()):
        raise http_exception_for(ErrorCode.INVALID_CAPTCHA)

    result = auth_service.login_student(body.school, body.studentId, body.password, now)
    if not result.ok:
        assert result.error_code is not None
        raise http_exception_for(result.error_code)

    user = repository.get_student_by_school_and_id(body.school, body.studentId)
    assert result.token is not None and user is not None
    auth_user = _auth_user(repository, user.id)
    assert auth_user is not None
    return LoginResponse(access_token=result.token, token_type="bearer", user=auth_user)


@router.post("/login/teacher", response_model=LoginResponse, summary="教师/管理员登录")
def login_teacher(
    body: TeacherLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    repository: Repository = Depends(get_repository),
    now: datetime = Depends(now_provider),
) -> LoginResponse:
    # 教师/管理员登录无需验证码。
    user = repository.get_user_by_account(body.account)
    if user is not None and user.role == "student":
        # 学生不得走教师入口登录。
        raise http_exception_for(ErrorCode.INVALID_CREDENTIALS)

    result = auth_service.login(body.account, body.password, now)
    if not result.ok:
        assert result.error_code is not None
        raise http_exception_for(result.error_code)

    assert result.token is not None and user is not None
    auth_user = _auth_user(repository, user.id)
    assert auth_user is not None
    return LoginResponse(access_token=result.token, token_type="bearer", user=auth_user)


# --------------------------------------------------------------------------- #
# 邮箱验证 + 改密（学生首次登录强制）                                            #
# --------------------------------------------------------------------------- #


@router.post("/email/send-code", response_model=SendCodeResponse, summary="发送邮箱验证码")
async def send_email_code(
    current: CurrentUser = Depends(get_current_user),
    repository: Repository = Depends(get_repository),
    email_service=Depends(get_email_service),
    verification: EmailVerificationService = Depends(get_email_verification_service),
) -> SendCodeResponse:
    user = repository.get_user(current.user_id)
    if user is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)
    if not validate_required(user.email) or not validate_email(user.email or "").ok:
        raise http_exception_for(
            ErrorCode.INVALID_EMAIL_FORMAT, message="邮箱缺失或格式不正确，请联系老师更正"
        )

    code = verification.generate(user.id)
    subject = "作业提交系统 - 邮箱验证码"
    body = (
        f"您好，{user.name or ''}\n\n"
        f"您的邮箱验证码为：{code}\n"
        f"验证码 10 分钟内有效，请在登录页完成邮箱验证与密码修改。\n\n"
        f"如非本人操作，请忽略本邮件。"
    )
    sent = await email_service.send_message(user.email, subject, body)
    if not sent:
        raise http_exception_for(
            ErrorCode.STORAGE_FAILED, message="验证码邮件发送失败，请稍后重试"
        )
    return SendCodeResponse(status="ok", email=_mask_email(user.email))


@router.post("/email/verify", summary="校验邮箱验证码并修改密码")
def verify_email(
    body: VerifyEmailRequest,
    current: CurrentUser = Depends(get_current_user),
    repository: Repository = Depends(get_repository),
    verification: EmailVerificationService = Depends(get_email_verification_service),
) -> dict[str, Any]:
    user = repository.get_user(current.user_id)
    if user is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)
    if not verification.verify(user.id, body.code):
        raise http_exception_for(ErrorCode.INVALID_CAPTCHA, message="验证码错误或已过期")
    if not validate_required(body.newPassword) or len(body.newPassword.strip()) < 6:
        raise http_exception_for(
            ErrorCode.MISSING_REQUIRED_FIELD, message="新密码不能为空且至少 6 位"
        )

    with repository.transaction():
        user.password = body.newPassword.strip()
        user.email_verified = True
    auth_user = _auth_user(repository, user.id)
    assert auth_user is not None
    return {"status": "ok", "user": auth_user}
