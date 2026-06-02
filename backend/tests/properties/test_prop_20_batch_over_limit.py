# Feature: homework-upload-system, Property 20: 批量超上限整体拒绝
"""Property 20：批量超上限整体拒绝。

依据 design.md「Correctness Properties」Property 20：

    *For any* 记录数超过 1000 的批量请求，整个请求应被拒绝、不创建任何用户，
    并返回"记录数量超过上限错误"（:attr:`ErrorCode.BATCH_LIMIT_EXCEEDED`）。

**Validates: Requirements 3.5**

测试策略：

* :data:`~app.services.user_service.MAX_BATCH_SIZE` 为 1000；本属性聚焦「记录数
  超过上限」这一**唯一**拒绝理由，因此生成的每条记录都构造为「合法外观」
  （角色合法、账号唯一、邮箱合法），以隔离被测属性——避免逐条校验（角色/邮箱/
  必填/重复）成为拒绝的混淆因素。即便如此，整体拒绝必须先于任何逐条处理发生。
* 记录数从 ``1001..1100`` 抽样：既严格大于 1000（触发整体拒绝），又把每个 example
  构造的记录列表规模控制在 ~1001 附近以约束单例成本。
  ``batch_create_users`` 在记录数超过上限时会**先**短路返回，不进入任何事务/写入，
  故该测试运行成本低，可保持 ``max_examples=100``。
* 每个 example 在测试体内构造一套全新的内存 SQLite 引擎 + 会话 + Repository，
  确保示例之间状态隔离、互不污染。
* 断言：返回 ``error_code == BATCH_LIMIT_EXCEEDED``；``success_count == 0`` 且
  ``failure_count == 0``（整体拒绝、零创建）；并直接查询数据库确认 **零用户被创建**
  （总数为 0，且任一样本账号查不到记录）。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import User
from app.repository import Repository
from app.services.user_service import (
    MAX_BATCH_SIZE,
    BatchResult,
    CreateUserCommand,
    UserService,
)

# 记录数：严格大于上限（1000），上界 1100 以约束每个 example 的构造成本。
_over_limit_counts = st.integers(min_value=MAX_BATCH_SIZE + 1, max_value=MAX_BATCH_SIZE + 100)


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


def _make_records(count: int) -> list[CreateUserCommand]:
    """构造 ``count`` 条「合法外观」且账号互不相同的记录。

    每条记录角色合法（Student）、账号唯一（``a{i}``）、邮箱合法（``u@e.com``），
    使整体拒绝成为唯一可能的拒绝理由（隔离被测属性）。
    """
    return [
        CreateUserCommand(role="Student", account=f"a{i}", email="u@e.com")
        for i in range(count)
    ]


@pytest.mark.property
@settings(max_examples=100)
@given(count=_over_limit_counts)
def test_batch_over_limit_is_rejected_with_zero_created(count: int) -> None:
    """记录数 > 1000 的批量请求必被整体拒绝（BATCH_LIMIT_EXCEEDED）且零创建。"""
    assert count > MAX_BATCH_SIZE  # 前置条件：确实超过上限。

    gen = _fresh_service()
    service, repo = next(gen)
    try:
        records = _make_records(count)
        assert len(records) == count  # 确认构造了超上限规模的请求。

        result: BatchResult = service.batch_create_users(records)

        # 1) 整体拒绝并返回「记录数量超过上限错误」（需求 3.5）。
        assert result.error_code == ErrorCode.BATCH_LIMIT_EXCEEDED

        # 2) 零创建、零失败明细（整体拒绝语义）。
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.failures == []

        # 3) 数据库侧确认确实未创建任何用户。
        total_users = repo.session.scalar(select(func.count()).select_from(User))
        assert total_users == 0, "整体拒绝不应创建任何用户记录"
        # 抽样账号也应查不到（额外印证零创建）。
        assert repo.get_user_by_account("a0") is None
        assert repo.get_user_by_account("a1") is None
    finally:
        gen.close()
