"""用户管理路由（admin / teacher 账号）。

提供前端用户管理页所需的全量 CRUD 与批量创建：

* ``GET /users`` —— 列出全部 admin / teacher 用户（管理员可见）。
* ``POST /users`` —— 创建用户（密码留空则默认 ``minglog666``）。
* ``PUT /users/{user_id}`` —— 更新用户。
* ``DELETE /users/{user_id}`` —— 删除用户。
* ``POST /users/batch`` —— 批量创建用户，返回成功数与逐条失败明细。

角色门控：均要求 admin 已认证（用户管理为管理员职能）。
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.api.deps import get_repository
from app.api.errors import http_exception_for
from app.api.serializers import serialize_user
from app.core.errors import ErrorCode
from app.core.validators import DEFAULT_PASSWORD, validate_email, validate_required
from app.repository import Repository

__all__ = ["router"]

router = APIRouter(prefix="/users", tags=["users"])

_MANAGED_ROLES = {"admin", "teacher"}


class UserPayload(BaseModel):
    role: str = Field(..., description="用户角色：admin / teacher")
    account: str = Field(..., description="登录账号（系统内唯一）")
    name: str = Field(default="", description="姓名")
    email: str = Field(..., description="邮箱（必填）")
    password: str = Field(default="", description="密码，留空默认 minglog666")


class BatchCreateRequest(BaseModel):
    records: list[UserPayload] = Field(default_factory=list)


class BatchFailureModel(BaseModel):
    row_id: int | str
    reason: str


class BatchResultResponse(BaseModel):
    success_count: int
    failure_count: int
    failures: list[BatchFailureModel] = Field(default_factory=list)


def _validate_payload(repo: Repository, body: UserPayload, *, exclude_id: Optional[str] = None) -> Optional[ErrorCode]:
    if not validate_required(body.role) or not validate_required(body.account):
        return ErrorCode.MISSING_REQUIRED_FIELD
    if body.role not in _MANAGED_ROLES:
        return ErrorCode.INVALID_ROLE
    # 邮箱为必填项。
    if not validate_required(body.email):
        return ErrorCode.MISSING_REQUIRED_FIELD
    if not validate_email(body.email).ok:
        return ErrorCode.INVALID_EMAIL_FORMAT
    if repo.account_exists(body.account, exclude_id=exclude_id):
        return ErrorCode.DUPLICATE_ACCOUNT
    return None


@router.get("", summary="用户列表")
def list_users(
    _user=Depends(require_roles("admin")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    users = repository.list_users(roles=list(_MANAGED_ROLES))
    return [serialize_user(u) for u in users]


@router.post("", summary="创建用户")
def create_user(
    body: UserPayload,
    _user=Depends(require_roles("admin")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    error = _validate_payload(repository, body)
    if error is not None:
        raise http_exception_for(error)
    password = body.password.strip() or DEFAULT_PASSWORD
    with repository.transaction():
        user = repository.create_user(
            role=body.role,
            account=body.account.strip(),
            name=body.name.strip(),
            email=body.email.strip(),
            password=password,
        )
    return serialize_user(user)


@router.put("/{user_id}", summary="更新用户")
def update_user(
    user_id: str,
    body: UserPayload,
    _user=Depends(require_roles("admin")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    user = repository.get_user(user_id)
    if user is None or user.role not in _MANAGED_ROLES:
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD, message="用户不存在")
    error = _validate_payload(repository, body, exclude_id=user_id)
    if error is not None:
        raise http_exception_for(error)
    with repository.transaction():
        user.role = body.role
        user.account = body.account.strip()
        user.name = body.name.strip()
        user.email = body.email.strip()
        # 密码留空时保留原密码；否则更新。
        if body.password.strip():
            user.password = body.password.strip()
    return serialize_user(user)


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: str,
    _user=Depends(require_roles("admin")),
    repository: Repository = Depends(get_repository),
) -> dict[str, str]:
    with repository.transaction():
        repository.delete_user(user_id)
    return {"status": "ok"}


@router.post("/batch", response_model=BatchResultResponse, summary="批量创建用户")
def batch_create_users(
    body: BatchCreateRequest,
    _user=Depends(require_roles("admin")),
    repository: Repository = Depends(get_repository),
) -> BatchResultResponse:
    if not body.records:
        raise http_exception_for(ErrorCode.EMPTY_BATCH)

    failures: list[BatchFailureModel] = []
    success = 0
    seen_accounts: set[str] = set()
    with repository.transaction():
        for index, rec in enumerate(body.records):
            error = _validate_payload(repository, rec)
            if error is None and rec.account.strip() in seen_accounts:
                error = ErrorCode.DUPLICATE_ACCOUNT
            if error is not None:
                failures.append(BatchFailureModel(row_id=index, reason=error.value))
                continue
            repository.create_user(
                role=rec.role,
                account=rec.account.strip(),
                name=rec.name.strip(),
                email=rec.email.strip(),
                password=rec.password.strip() or DEFAULT_PASSWORD,
            )
            seen_accounts.add(rec.account.strip())
            success += 1
    return BatchResultResponse(
        success_count=success, failure_count=len(failures), failures=failures
    )
