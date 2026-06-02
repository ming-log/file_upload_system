"""属性测试：Property 4 - 凭据不匹配则登录失败且不签发令牌。

依据 design.md「Correctness Properties」Property 4 与需求 1.2：

    *For any* 用户库与一组登录凭据，若账号不存在或密码与已存储凭据不匹配，
    则登录被拒绝、不返回令牌，并返回"账号或密码错误"（INVALID_CREDENTIALS）。

被测对象：:class:`app.services.auth_service.AuthService.login`。

为避免触发其它分支的错误码，生成器刻意约束输入空间：

* 账号与密码均**非空白**（``validate_required`` 通过），从而不会触发
  ``MISSING_REQUIRED_FIELD``。
* 场景二中已存储密码**非空**，从而不会触发 ``PASSWORD_RESET_REQUIRED``；
  且通过 ``assume`` 保证提供的密码 != 已存储密码。

覆盖两类场景（由 Hypothesis 同时生成）：

1. 账号不存在：用户库为空（不创建用户），以非空账号/密码登录。
2. 账号存在但密码错误：创建一个非空存储密码的用户，以不同的非空密码登录。
"""

# Feature: homework-upload-system, Property 4: 凭据不匹配则登录失败且不签发令牌

from __future__ import annotations

from datetime import datetime

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.auth_service import AuthService

# 固定的登录时刻；本属性仅关心凭据匹配失败，与具体时间无关。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 非空白字符串：strip() 后仍非空，确保 validate_required 通过。
_non_blank_text = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")

# 角色取值（仅用于落库的用户记录，对本属性无影响）。
_roles = st.sampled_from(["Admin", "Teacher", "Student"])


def _make_repository() -> Repository:
    """构造绑定到独立内存 SQLite 的 Repository（每个示例隔离建表）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    return Repository(session)


@pytest.mark.property
@settings(max_examples=100)
@given(
    account=_non_blank_text,
    provided_password=_non_blank_text,
)
def test_login_rejected_when_account_does_not_exist(
    account: str, provided_password: str
) -> None:
    """场景一：账号不存在时登录失败、不签发令牌，返回 INVALID_CREDENTIALS。

    **Validates: Requirements 1.2**
    """
    repo = _make_repository()
    try:
        # 用户库为空：不创建任何用户，故 account 必然不存在。
        service = AuthService(repo)
        result = service.login(account=account, password=provided_password, now=_NOW)

        assert result.ok is False
        assert result.token is None
        assert result.error_code == ErrorCode.INVALID_CREDENTIALS
    finally:
        repo.session.close()


@pytest.mark.property
@settings(max_examples=100)
@given(
    account=_non_blank_text,
    role=_roles,
    stored_password=_non_blank_text,
    provided_password=_non_blank_text,
)
def test_login_rejected_when_password_mismatch(
    account: str, role: str, stored_password: str, provided_password: str
) -> None:
    """场景二：账号存在但密码不匹配时登录失败、不签发令牌，返回 INVALID_CREDENTIALS。

    存储密码非空（不触发 PASSWORD_RESET_REQUIRED），且提供密码 != 存储密码。

    **Validates: Requirements 1.2**
    """
    # 确保提供的密码与存储密码确实不同，从而构成"密码不匹配"。
    assume(provided_password != stored_password)

    repo = _make_repository()
    try:
        with repo.transaction():
            repo.create_user(
                role=role,
                account=account,
                password=stored_password,  # 非空存储密码
            )

        service = AuthService(repo)
        result = service.login(account=account, password=provided_password, now=_NOW)

        assert result.ok is False
        assert result.token is None
        assert result.error_code == ErrorCode.INVALID_CREDENTIALS
    finally:
        repo.session.close()
