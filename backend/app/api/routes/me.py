"""个人中心路由（当前登录用户的基本信息与改密）。

* ``GET /me`` —— 返回当前登录用户的完整基本信息（含头像、邮箱、是否已验证；
  学生附带学号、姓名、学校、班级）。
* ``PUT /me`` —— 更新当前用户**可改**的基本信息：头像 ``avatar`` 与邮箱 ``email``。
  姓名对教师/管理员可改；学生的学号与姓名由学校统一维护，**不允许自行修改**。
  修改邮箱后该邮箱的「已验证」状态会被重置（需重新走邮箱验证）。

改密走邮箱验证：复用 :mod:`app.api.routes.auth` 的
``POST /auth/email/send-code`` 与 ``POST /auth/email/verify``（提交验证码 + 新密码）。
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user, get_repository
from app.api.errors import http_exception_for
from app.core.errors import ErrorCode
from app.core.validators import validate_email, validate_required
from app.repository import Repository

__all__ = ["router"]

router = APIRouter(prefix="/me", tags=["me"])

# 头像 data URL 大小上限（约 1.5MB base64，足够常见头像）。
_MAX_AVATAR_CHARS = 1_500_000


class UpdateMeRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="姓名（教师/管理员可改；学生不可改）")
    email: Optional[str] = Field(default=None, description="电子邮箱")
    avatar: Optional[str] = Field(default=None, description="头像（base64 data URL），传空串可清除")


def _serialize_me(repo: Repository, user) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": user.id,
        "role": user.role,
        "account": user.account,
        "name": user.name or "",
        "email": user.email or "",
        "avatar": user.avatar or "",
        "emailVerified": bool(user.email_verified),
    }
    if user.role == "student":
        data["studentId"] = user.student_id or ""
        data["classId"] = user.class_id or ""
        clazz = repo.get_class(user.class_id) if user.class_id else None
        data["school"] = clazz.school if clazz is not None else ""
        if clazz is not None:
            data["className"] = f"{clazz.grade} {clazz.major}"
    return data


@router.get("", summary="获取当前用户信息")
def get_me(
    current: CurrentUser = Depends(get_current_user),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    user = repository.get_user(current.user_id)
    if user is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)
    return _serialize_me(repository, user)


@router.put("", summary="更新当前用户基本信息")
def update_me(
    body: UpdateMeRequest,
    current: CurrentUser = Depends(get_current_user),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    user = repository.get_user(current.user_id)
    if user is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)

    # 邮箱：若提供则校验格式；修改邮箱将重置验证状态。
    if body.email is not None:
        new_email = body.email.strip()
        if not validate_required(new_email):
            raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD, message="邮箱不能为空")
        if not validate_email(new_email).ok:
            raise http_exception_for(ErrorCode.INVALID_EMAIL_FORMAT)

    # 头像：限制大小，传空串表示清除。
    if body.avatar is not None and len(body.avatar) > _MAX_AVATAR_CHARS:
        raise http_exception_for(
            ErrorCode.FILE_TOO_LARGE, message="头像图片过大，请压缩后重试"
        )

    # 姓名：仅教师/管理员可改；学生姓名由学校维护，忽略其改名请求。
    with repository.transaction():
        if body.name is not None and user.role in {"admin", "teacher"}:
            if validate_required(body.name):
                user.name = body.name.strip()
        if body.email is not None:
            new_email = body.email.strip()
            if new_email != (user.email or ""):
                user.email = new_email
                # 邮箱变更后需重新验证。
                user.email_verified = False
        if body.avatar is not None:
            user.avatar = body.avatar.strip() or None

    return _serialize_me(repository, user)
