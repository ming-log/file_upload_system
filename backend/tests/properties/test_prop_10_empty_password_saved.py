# Feature: homework-upload-system, Property 10: 空密码用户允许保存
"""Property 10：空密码用户允许保存。

依据 design.md「Correctness Properties」Property 10：

    *For any* 其余字段合法但密码字段为空的用户记录，创建应成功保存该记录。

**Validates: Requirements 2.4**

测试策略：
对任意「其余字段合法、密码为空（``None`` 或 ``""``）」的用户记录，调用
:meth:`UserService.create_user` 应成功（``result.ok is True``），且记录被持久化——
通过 :meth:`Repository.get_user_by_account` 能取回该用户，且其 ``password`` 等于
传入的空值（``None`` 或 ``""``）。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的
内存引擎 + 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``），从而避免账号唯一性在多用例间相互污染。
"""

from __future__ import annotations

from typing import Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import CreateUserCommand, UserService

# 合法角色集合（需求 2.2 / 2.7）。
_VALID_ROLES = ["Admin", "Teacher", "Student"]

# 非空账号：非空、非纯空白字符串（满足 validate_required，需求 2.6）。
# 用 .strip() 去空白后再过滤掉空串，确保账号有效。
_accounts = st.text(min_size=1, max_size=32).map(lambda s: s.strip()).filter(lambda s: s != "")

# “域名标签”片段：不含 '@' 与 '.'，用于拼出带点的合法域名（需求 2.5）。
_domain_labels = st.text(
    alphabet=st.characters(blacklist_characters="@."),
    min_size=1,
    max_size=6,
)


@st.composite
def _valid_emails(draw: st.DrawFn) -> str:
    """构造满足 validate_email 的合法邮箱：local + '@' + 至少含一个点号的域名。"""
    local = draw(
        st.text(alphabet=st.characters(blacklist_characters="@"), min_size=1, max_size=8)
    )
    labels = draw(st.lists(_domain_labels, min_size=2, max_size=4))
    domain = ".".join(labels)
    return f"{local}@{domain}"


# 空密码：仅 None 或空串两种取值（需求 2.4）。
_empty_passwords = st.sampled_from([None, ""])


@pytest.mark.property
@settings(max_examples=100)
@given(
    role=st.sampled_from(_VALID_ROLES),
    account=_accounts,
    email=_valid_emails(),
    password=_empty_passwords,
)
def test_empty_password_user_is_saved(
    role: str, account: str, email: str, password: Optional[str]
) -> None:
    """空密码（None/""）的合法用户应创建成功并被持久化，且 password 保持空值。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离（账号唯一性不被污染）。
    engine = create_db_engine()
    create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        repo = Repository(session)
        service = UserService(repo)

        result = service.create_user(
            CreateUserCommand(
                role=role,
                account=account,
                email=email,
                password=password,
            )
        )

        # 创建应成功（需求 2.4：空密码允许保存）。
        assert result.ok is True, f"空密码用户创建失败：error_code={result.error_code}"

        # 记录应被持久化：可按账号取回。
        saved = repo.get_user_by_account(account)
        assert saved is not None, "空密码用户未被持久化"
        # password 保持传入的空值（None 或 ""）。
        assert saved.password == password
    finally:
        session.close()
        engine.dispose()
