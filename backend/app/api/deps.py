"""FastAPI 依赖注入工具（认证、持久化、存储接线）。

为对接前端（Figma 重写版）的全量 CRUD 接口，本模块提供精简而完整的依赖项：

* **持久化**：模块级默认引擎 + 会话工厂；:func:`get_session` 产出请求级会话，
  :func:`get_repository` 包装为 :class:`~app.repository.Repository`。
* **认证**：:func:`get_auth_service` 构造认证服务；:func:`get_current_user` 从
  ``Authorization: Bearer <token>`` 解析并校验令牌；:func:`require_roles` 做角色门控。
* **存储**：:func:`get_storage_service` 默认返回 :class:`LocalDiskStorageService`
  （本地磁盘，零外部依赖），可经环境变量 ``STORAGE_BACKEND=minio`` 切换为 MinIO。

角色统一使用小写：``admin`` / ``teacher`` / ``student``，与前端 ``Role`` 类型一致。
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import load_app_env

# 尽早加载 .env，使下方存储/邮件/认证按需读取环境变量时配置已生效。
load_app_env()

from app.adapters.email_service import EmailService
from app.adapters.storage_service import (
    LocalDiskStorageService,
    MinioStorageService,
    StorageService,
)
from app.api.middleware import parse_bearer_token
from app.core.errors import ErrorCode
from app.db import (
    DEFAULT_DATABASE_URL,
    create_all,
    create_db_engine,
    create_session_factory,
)
from app.repository import Repository
from app.services.auth_service import AuthService
from app.services.captcha_service import CaptchaService

__all__ = [
    "CurrentUser",
    "utcnow",
    "to_naive_utc",
    "get_engine",
    "get_session",
    "get_repository",
    "get_auth_service",
    "get_current_user",
    "require_roles",
    "get_storage_service",
    "get_email_service",
    "get_captcha_service",
]


# --------------------------------------------------------------------------- #
# 当前用户上下文                                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CurrentUser:
    """已认证用户的请求级上下文。"""

    role: str
    account: str


# --------------------------------------------------------------------------- #
# 时间提供者                                                                    #
# --------------------------------------------------------------------------- #


def utcnow() -> datetime:
    """返回当前 UTC 时间（aware）。"""
    return datetime.now(timezone.utc)


def to_naive_utc(value: datetime) -> datetime:
    """将 datetime 归一化为 naive-UTC（去除时区信息）。"""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# --------------------------------------------------------------------------- #
# 持久化接线                                                                    #
# --------------------------------------------------------------------------- #

# 默认数据库连接串：优先 DATABASE_URL，缺省回退到项目内文件 SQLite（持久化数据）。
_DEFAULT_SQLITE = "sqlite+pysqlite:///./homework.db"
_DATABASE_URL: str = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)

_engine: Engine = create_db_engine(_DATABASE_URL)
create_all(_engine)
_session_factory = create_session_factory(_engine)


def get_engine() -> Engine:
    return _engine


def get_session() -> Iterator[Session]:
    """产出请求级数据库会话，并在请求结束后关闭。"""
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def get_repository(session: Session = Depends(get_session)) -> Repository:
    return Repository(session)


def get_auth_service(repository: Repository = Depends(get_repository)) -> AuthService:
    return AuthService(repository)


# --------------------------------------------------------------------------- #
# 存储 / 邮件接线                                                               #
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _default_storage_service() -> StorageService:
    """构造（并缓存）默认存储服务：本地磁盘，或经环境变量切换为 MinIO。"""
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if backend == "minio":
        return MinioStorageService()
    return LocalDiskStorageService()


@lru_cache(maxsize=1)
def _default_email_service() -> EmailService:
    return EmailService()


@lru_cache(maxsize=1)
def _default_captcha_service() -> CaptchaService:
    """构造（并缓存）进程级验证码服务，使生成与校验共享同一内存存储。"""
    return CaptchaService()


def get_storage_service() -> StorageService:
    return _default_storage_service()


def get_email_service() -> EmailService:
    return _default_email_service()


def get_captcha_service() -> CaptchaService:
    return _default_captcha_service()


# --------------------------------------------------------------------------- #
# 认证注入                                                                      #
# --------------------------------------------------------------------------- #


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    now: datetime = Depends(utcnow),
) -> CurrentUser:
    """解析并校验 Bearer 令牌，注入当前用户上下文；失败返回 401。"""
    token = parse_bearer_token(authorization)
    result = auth_service.verify_token(token, now=now)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": ErrorCode.UNAUTHENTICATED.value,
                "message": "未认证：令牌缺失、无效或已过期",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(role=result.role, account=result.account)


def require_roles(*roles: str) -> Callable[..., CurrentUser]:
    """构造角色门控依赖；角色不匹配返回 403。"""
    allowed = frozenset(roles)

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": ErrorCode.FORBIDDEN.value,
                    "message": "权限不足：当前角色无权访问该资源",
                },
            )
        return current_user

    return _dependency
