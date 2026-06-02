# Feature: homework-upload-system, Property 5: 空存储密码拒绝密码登录
"""Property 5: 空存储密码拒绝密码登录。

依据 design.md「Correctness Properties」Property 5 与需求 1.5：

    *For any* 存储密码字段为空（``None`` 或 ``""``）的用户，使用任意**非空**
    密码进行密码登录都应被拒绝，并返回“需要重置密码”
    （:attr:`ErrorCode.PASSWORD_RESET_REQUIRED`），且不签发令牌。

测试策略
--------

* 在测试体内构造**全新的内存 SQLite 引擎 + Repository**，确保每个样例彼此隔离、
  无状态泄漏。
* 角色从 ``{Admin, Teacher, Student}`` 采样；账号为非空字符串；邮箱为合法格式；
  存储密码从 ``{None, ""}`` 采样并提交。
* 登录尝试密码生成为**非空白**字符串，避免触发 ``MISSING_REQUIRED_FIELD``
  （需求 1.6），从而精确验证“空存储密码”这一条路径。

**Validates: Requirements 1.5**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.auth_service import AuthService

# 采样自合法角色集合（与 validators.VALID_ROLES 一致）。
_role_strategy = st.sampled_from(["Admin", "Teacher", "Student"])

# 非空账号：去除首尾空白后非空，确保通过必填校验。
_account_strategy = st.text(min_size=1).filter(lambda s: s.strip() != "")

# 存储密码为空：None 或空字符串，两者都应触发 PASSWORD_RESET_REQUIRED。
_empty_password_strategy = st.sampled_from([None, ""])

# 登录尝试密码：非空白字符串，避免触发 MISSING_REQUIRED_FIELD。
_attempt_password_strategy = st.text(min_size=1).filter(lambda s: s.strip() != "")


@pytest.mark.property
@settings(max_examples=100)
@given(
    role=_role_strategy,
    account=_account_strategy,
    stored_password=_empty_password_strategy,
    attempt_password=_attempt_password_strategy,
    now=st.datetimes(),
)
def test_empty_stored_password_rejects_password_login(
    role: str,
    account: str,
    stored_password,
    attempt_password: str,
    now,
) -> None:
    """存储密码为空的用户，任意非空密码登录都应被拒绝并要求重置密码。"""
    # 全新内存引擎 + 仓储，保证样例间隔离。
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)
        with repo.transaction():
            repo.create_user(
                role=role,
                account=account,
                email="user@example.com",
                password=stored_password,
            )

        result = AuthService(repo).login(account, attempt_password, now)

        assert result.ok is False
        assert result.token is None
        assert result.error_code == ErrorCode.PASSWORD_RESET_REQUIRED
    finally:
        session.close()
