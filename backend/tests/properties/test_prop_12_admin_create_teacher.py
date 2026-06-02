# Feature: homework-upload-system, Property 12: Admin 创建教师返回教师账号
"""Property 12：Admin 创建教师返回教师账号。

依据 design.md「Correctness Properties」Property 12：

    *For any* 角色为 Admin 的请求与非空合法 ``account``、``email``，创建应成功
    生成一个 ``role == Teacher`` 的用户，并返回该用户的 ``account`` 标识。

**Validates: Requirements 4.1, 4.3**

测试策略：

* 生成一个非空白的 ``account``（可打印的非空白 ASCII，码点 33..126，长度 1..20，
  落在 ``User.account`` 存储宽度内并保证 ``validate_required`` 通过）与一个一定
  合法的邮箱（``local@domain.com`` 形式：恰好一个 ``@``、本地名非空、域名非空且
  含点号），以隔离被测属性，避免被必填/邮箱格式校验干扰。
* 每个 example 在测试体内构造一套全新的内存 SQLite 引擎 + 会话 + Repository，
  确保示例之间状态隔离、互不污染。
* 以 ``current_role="Admin"`` 调用
  :meth:`app.services.user_service.UserService.create_teacher`，断言创建成功
  （``ok is True``、``error_code is None``）且返回的 ``account`` 等于入参
  （需求 4.3）。
* 再通过 :meth:`Repository.get_user_by_account` 读回该用户，断言其存在、
  ``role == "Teacher"``（需求 4.1）且 ``account`` 与入参一致（需求 4.3）。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import UserService

# 非空白账号：可打印的非空白 ASCII（码点 33..126），保证 validate_required 通过；
# 长度 1..20，落在 User.account 的存储宽度内。
_accounts = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 邮箱片段：仅小写字母，用于拼出一定合法的邮箱 local@domain.com。
_email_parts = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=8,
)


@st.composite
def _valid_emails(draw: st.DrawFn) -> str:
    """构造一定满足邮箱格式（恰好一个 @、本地名非空、域名非空且含点号）的邮箱。"""
    local = draw(_email_parts)
    domain = draw(_email_parts)
    return f"{local}@{domain}.com"


def _fresh_service() -> Iterator[tuple[UserService, Repository]]:
    """构造一套全新的内存 SQLite 引擎/会话/Repository/UserService（每个 example 隔离）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    repo = Repository(session)
    try:
        yield UserService(repo), repo
    finally:
        session.close()
        engine.dispose()


@pytest.mark.property
@settings(max_examples=100)
@given(account=_accounts, email=_valid_emails())
def test_admin_create_teacher_returns_teacher_account(account: str, email: str) -> None:
    """Admin 以非空合法 account/email 创建教师应成功，生成 Teacher 用户并返回其 account。"""
    gen = _fresh_service()
    service, repo = next(gen)
    try:
        result = service.create_teacher("Admin", account, email)

        # 创建成功并返回该教师账号（需求 4.3）。
        assert result.ok is True, f"Admin 创建教师应成功，但得到 {result.error_code}"
        assert result.error_code is None
        assert result.account == account

        # 读回被创建用户：存在、角色为 Teacher（需求 4.1），account 一致（需求 4.3）。
        stored = repo.get_user_by_account(account)
        assert stored is not None, "创建后应能按 account 读回该用户"
        assert stored.role == "Teacher"
        assert stored.account == account
    finally:
        # 触发 finally 块以关闭会话并释放引擎。
        gen.close()
