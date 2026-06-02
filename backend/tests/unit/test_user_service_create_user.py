"""UserService.create_user 的示例 / 边界单元测试（任务 7.1）。

与属性测试（tests/properties/，任务 7.2 / 7.3）互补：本文件以**具体示例与边界值**
覆盖 ``app.services.user_service.UserService.create_user`` 的关键路径与校验顺序。

来源依据（需求 2）：
- 2.1 创建用户存储 role/account/email/password；
- 2.2 / 2.7 角色取值限定与无效角色拒绝；
- 2.3 账号唯一性（重复拒绝且不修改既有记录）；
- 2.4 空密码允许保存；
- 2.5 邮箱格式校验；
- 2.6 必填字段（role/account）缺失拒绝。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import User
from app.repository import Repository
from app.services.user_service import (
    CreateUserCommand,
    CreateUserResult,
    UserService,
)


@pytest.fixture()
def repo() -> Iterator[Repository]:
    """提供绑定到独立内存 SQLite 的 Repository（每个测试隔离）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield Repository(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def service(repo: Repository) -> UserService:
    """基于隔离仓储构造 UserService。"""
    return UserService(repo)


# --------------------------------------------------------------------------- #
# 成功路径（需求 2.1）                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role", ["Admin", "Teacher", "Student"])
def test_create_user_success_persists_all_fields(
    service: UserService, repo: Repository, role: str
) -> None:
    """合法输入应创建成功，并持久化 role/account/email/password（需求 2.1）。"""
    cmd = CreateUserCommand(
        role=role,
        account=f"acc_{role}",
        email="user@example.com",
        password="secret",
    )

    result = service.create_user(cmd)

    assert result.ok is True
    assert result.error_code is None
    assert result.user_id is not None
    assert result.account == f"acc_{role}"

    stored = repo.get_user_by_account(f"acc_{role}")
    assert stored is not None
    assert stored.role == role
    assert stored.account == f"acc_{role}"
    assert stored.email == "user@example.com"
    assert stored.password == "secret"


# --------------------------------------------------------------------------- #
# 必填字段缺失（需求 2.6）                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role,account", [("", "acc"), ("   ", "acc"), (None, "acc")])
def test_create_user_missing_role(service: UserService, role, account: str) -> None:
    """role 为空/纯空白/None 应返回 MISSING_REQUIRED_FIELD（需求 2.6）。"""
    result = service.create_user(
        CreateUserCommand(role=role, account=account, email="u@e.com")  # type: ignore[arg-type]
    )
    assert result.ok is False
    assert result.error_code is ErrorCode.MISSING_REQUIRED_FIELD


@pytest.mark.unit
@pytest.mark.parametrize("account", ["", "   ", None])
def test_create_user_missing_account(service: UserService, account) -> None:
    """account 为空/纯空白/None 应返回 MISSING_REQUIRED_FIELD（需求 2.6）。"""
    result = service.create_user(
        CreateUserCommand(role="Teacher", account=account, email="u@e.com")  # type: ignore[arg-type]
    )
    assert result.ok is False
    assert result.error_code is ErrorCode.MISSING_REQUIRED_FIELD


@pytest.mark.unit
def test_create_user_missing_field_creates_no_record(
    service: UserService, repo: Repository
) -> None:
    """必填缺失时不应创建任何用户记录。"""
    service.create_user(CreateUserCommand(role="", account="", email="u@e.com"))
    assert repo.session.scalar(select(User).limit(1)) is None


# --------------------------------------------------------------------------- #
# 角色取值无效（需求 2.2 / 2.7）—— 校验顺序在邮箱之前                            #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role", ["admin", "teacher", "ROOT", "guest"])
def test_create_user_invalid_role(service: UserService, role: str) -> None:
    """非法角色应返回 INVALID_ROLE（需求 2.2 / 2.7）。"""
    result = service.create_user(
        CreateUserCommand(role=role, account="acc", email="u@e.com")
    )
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_ROLE


@pytest.mark.unit
def test_create_user_invalid_role_precedes_email_check(service: UserService) -> None:
    """同时角色非法且邮箱非法时，应优先返回 INVALID_ROLE（校验顺序）。"""
    result = service.create_user(
        CreateUserCommand(role="root", account="acc", email="bad-email")
    )
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_ROLE


# --------------------------------------------------------------------------- #
# 邮箱格式校验（需求 2.5）                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("email", ["bad-email", "@e.com", "u@", "u@e", "a@@b.com"])
def test_create_user_invalid_email(service: UserService, email: str) -> None:
    """非法邮箱应返回 INVALID_EMAIL_FORMAT（需求 2.5）。"""
    result = service.create_user(
        CreateUserCommand(role="Student", account="acc", email=email)
    )
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_EMAIL_FORMAT


@pytest.mark.unit
@pytest.mark.parametrize("email", [None, ""])
def test_create_user_empty_email_treated_as_invalid_format(
    service: UserService, email
) -> None:
    """设计取舍：通用 create_user 对空邮箱判为格式非法（而非必填缺失）。"""
    result = service.create_user(
        CreateUserCommand(role="Student", account="acc", email=email)  # type: ignore[arg-type]
    )
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_EMAIL_FORMAT


# --------------------------------------------------------------------------- #
# 账号唯一性（需求 2.3）                                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_create_user_duplicate_account_rejected(
    service: UserService, repo: Repository
) -> None:
    """重复账号应返回 DUPLICATE_ACCOUNT，且不修改既有记录（需求 2.3）。"""
    first = service.create_user(
        CreateUserCommand(role="Teacher", account="dup", email="first@e.com", password="p1")
    )
    assert first.ok is True

    second = service.create_user(
        CreateUserCommand(role="Student", account="dup", email="second@e.com", password="p2")
    )
    assert second.ok is False
    assert second.error_code is ErrorCode.DUPLICATE_ACCOUNT

    # 既有记录保持不变（仍是第一次创建的内容），且系统内仅有一条该账号记录。
    users = list(repo.session.scalars(select(User).where(User.account == "dup")).all())
    assert len(users) == 1
    assert users[0].role == "Teacher"
    assert users[0].email == "first@e.com"
    assert users[0].password == "p1"


# --------------------------------------------------------------------------- #
# 空密码允许保存（需求 2.4）                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("password", [None, ""])
def test_create_user_empty_password_saved(
    service: UserService, repo: Repository, password
) -> None:
    """密码为空/None 仍应成功保存用户记录（需求 2.4）。"""
    result = service.create_user(
        CreateUserCommand(role="Student", account="nopwd", email="u@e.com", password=password)
    )
    assert result.ok is True

    stored = repo.get_user_by_account("nopwd")
    assert stored is not None
    assert stored.password == password


# --------------------------------------------------------------------------- #
# 结果类型自洽性                                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_create_user_result_rejects_inconsistent_states() -> None:
    """CreateUserResult：成功不可带错误码；失败必须带错误码。"""
    with pytest.raises(ValueError):
        CreateUserResult(ok=True, error_code=ErrorCode.DUPLICATE_ACCOUNT)
    with pytest.raises(ValueError):
        CreateUserResult(ok=False, error_code=None)
