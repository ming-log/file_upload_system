# Feature: homework-upload-system, Property 9: 账号唯一性不可破坏
"""Property 9：账号唯一性不可破坏。

依据 design.md「Correctness Properties」Property 9：

    *For any* 已含用户的系统与一个已存在的 ``account``，再次以该 ``account``
    创建用户应被拒绝、原有用户记录保持不变，并返回“账号重复错误”
    （:attr:`ErrorCode.DUPLICATE_ACCOUNT`）。

**Validates: Requirements 2.3**

测试策略：

* 生成一个非空白的 ``account`` 与两份共享该 ``account`` 的合法用户载荷
  （角色取自 ``{Admin, Teacher, Student}``、邮箱形如 ``local@domain.com``、
  密码可空），以隔离“账号唯一性”这一被测属性，避免被其它校验（角色/邮箱/
  必填）干扰。
* 每个 example 在测试体内构造一套全新的内存 SQLite 引擎 + 会话 + Repository，
  确保示例之间状态隔离、互不污染（不使用 ``@given`` 上的函数级 fixture 注入
  数据库状态）。
* 先创建第一位用户（断言成功）；再以相同 ``account`` 创建第二位用户，断言被
  拒绝且错误码为 ``DUPLICATE_ACCOUNT``；最后断言系统内该 ``account`` 恰好仅有
  一条记录，且其字段与第一次创建时完全一致（原记录未被修改）。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import User
from app.repository import Repository
from app.services.user_service import CreateUserCommand, UserService

# 合法角色：取自 {Admin, Teacher, Student}，使 create_user 通过角色校验。
_roles = st.sampled_from(["Admin", "Teacher", "Student"])

# 非空白账号：可打印的非空白 ASCII（codepoint 33..126），保证 validate_required 通过；
# 长度 1..20，落在 User.account 的 String(64) 存储宽度内。
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


# 密码：允许为空（None / 空串）或任意短字符串（需求 2.4 允许空密码保存）。
_passwords = st.one_of(st.none(), st.text(max_size=12))


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
@given(
    account=_accounts,
    role1=_roles,
    email1=_valid_emails(),
    password1=_passwords,
    role2=_roles,
    email2=_valid_emails(),
    password2=_passwords,
)
def test_account_uniqueness_is_unbreakable(
    account: str,
    role1: str,
    email1: str,
    password1: Optional[str],
    role2: str,
    email2: str,
    password2: Optional[str],
) -> None:
    """以同一 account 二次创建用户必被拒绝（DUPLICATE_ACCOUNT），原记录不变、零新增。"""
    gen = _fresh_service()
    service, repo = next(gen)
    try:
        # 第一次创建：应成功（其余字段均合法，仅测试账号唯一性）。
        first = service.create_user(
            CreateUserCommand(
                role=role1, account=account, email=email1, password=password1
            )
        )
        assert first.ok is True, f"首次创建应成功，但得到 {first.error_code}"
        assert first.error_code is None
        assert first.account == account

        # 第二次创建：相同 account（角色/邮箱/密码可不同），应被拒绝。
        second = service.create_user(
            CreateUserCommand(
                role=role2, account=account, email=email2, password=password2
            )
        )
        assert second.ok is False, "相同 account 的二次创建必须被拒绝"
        assert second.error_code == ErrorCode.DUPLICATE_ACCOUNT
        assert second.user_id is None

        # 系统内该 account 恰好仅有一条记录（未创建新记录）。
        users = list(
            repo.session.scalars(select(User).where(User.account == account)).all()
        )
        assert len(users) == 1, "重复 account 不应产生新增记录"

        # 原有记录保持不变：字段仍等于第一次创建时的值。
        stored = users[0]
        assert stored.id == first.user_id
        assert stored.role == role1
        assert stored.account == account
        assert stored.email == email1
        assert stored.password == password1
    finally:
        # 触发 finally 块以关闭会话并释放引擎。
        gen.close()
