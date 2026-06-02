# Feature: homework-upload-system, Property 18: 批量创建处理全部有效记录
"""Property 18：批量创建处理全部有效记录。

依据 design.md「Correctness Properties」Property 18：

    *For any* 包含 1..1000 条记录的批量请求，所有有效记录（账号/学号在系统内唯一
    且批次内未重复、邮箱合法、必填非空）都应被创建，且无效记录被跳过并在失败明细
    中给出行标识/学号与原因。

**Validates: Requirements 3.1, 3.2, 6.5**

本测试覆盖 :meth:`app.services.user_service.UserService.batch_create_users` 这一
批量创建用户路径（需求 3.1 / 3.2）。批量导入学生（需求 6.5）走的是结构同构的
``batch_import_students``，其「全部有效记录被创建、无效记录跳过并报告」语义与本
属性一致，故本属性以 ``batch_create_users`` 为代表进行验证。

测试策略
--------

* **运行规模**：Property 18 声明的有效区间为 1..1000 条记录。为保持属性测试
  在 100+ 次迭代下的运行时间可控，本测试将单批记录数上限收敛到 **30**
  （``_MAX_RECORDS``）。该上限不改变被测属性——「逐条校验 + 首次出现去重 +
  失败收集」的语义与批量规模无关，30 条足以覆盖「有效/缺失/角色非法/邮箱非法/
  批次内重复」的各种交错组合。批次为空与超 1000 上限属于「整体拒绝」语义，由
  Property 20（任务 7.12）单独覆盖，不在本属性范围内。

* **构造即分类**：为避免与服务实现纠缠，测试通过「构造即知分类」的方式生成记录，
  并独立计算期望结果：

  - 有效记录（``valid``）：合法角色、唯一非空账号 ``v{k}``、合法邮箱。每条有效
    记录引入一个**全新且唯一**的账号，因此在批次内必为「首次出现」，依据 Property 18
    应被创建。
  - 必填缺失（``missing``）：账号为空白 -> ``MISSING_REQUIRED_FIELD``（需求 3.2 语义）。
  - 角色非法（``bad_role``）：非空唯一账号 ``x{k}`` + 非法角色 -> ``INVALID_ROLE``。
  - 邮箱非法（``bad_email``）：非空唯一账号 ``x{k}`` + 非法邮箱 -> ``INVALID_EMAIL_FORMAT``。
  - 账号重复（``dup``）：账号取自**此前已出现的某条有效记录**账号 ``v{j}``，邮箱合法
    -> ``DUPLICATE_ACCOUNT``（需求 3.2）。当此前尚无有效账号可复用时，退化为一条
    ``bad_email`` 无效记录，保证分类确定。

  账号命名空间互不重叠（``v*`` / ``x*`` / 空白），故有效记录与无效记录的账号绝不
  相撞，分类完全由构造决定。

* **隔离**：每个 example 在测试体内构造一套全新的内存 SQLite 引擎 + 会话 +
  Repository + UserService，确保示例之间状态隔离、互不污染。

期望断言（对应 Property 18 全部要点）：

1. ``result.error_code is None``（记录数落在 1..1000，按逐条处理而非整体拒绝）。
2. 每条「有效且首次出现唯一」记录都被创建：``repo.get_user_by_account(account)``
   非空；且 ``success_count`` 等于期望创建数。
3. 无效/重复记录未被创建（其专属 ``x*`` 账号查无记录），并出现在 ``failures``
   中——失败明细的 ``row_id``（0 基行索引）与 ``reason``（错误码）与构造时一致。
4. ``failure_count`` 等于无效/重复记录数，且 ``success_count + failure_count``
   等于记录总数（计数守恒的局部体现）。
"""

from __future__ import annotations

from typing import Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import CreateUserCommand, UserService

# 单批记录数上限：收敛到 30 以保证 100+ 次迭代的运行时间可控（见模块文档）。
_MAX_RECORDS = 30

# 合法角色：取自 {Admin, Teacher, Student}。
_roles = st.sampled_from(["Admin", "Teacher", "Student"])

# 非法角色：非空白且不属于 VALID_ROLES（注意大小写敏感，"admin" != "Admin"）。
_invalid_roles = st.sampled_from(
    ["admin", "ADMIN", "teacher", "TEACHER", "student", "user", "Guest", "root", "X"]
)

# 非法邮箱：均无法通过 validate_email（无 @ / 多个 @ / 本地名空 / 域名无点号 / 域名空）。
_invalid_emails = st.sampled_from(
    ["noatsign", "a@b@c.com", "@domain.com", "nodot@domaincom", "trailing@", ""]
)

# 空白账号：触发 MISSING_REQUIRED_FIELD（validate_required 将纯空白视为缺失）。
_blank_accounts = st.sampled_from(["", "   ", "\t", "  \n "])

# 邮箱片段：仅小写字母，用于拼出一定合法的邮箱 local@domain.com。
_email_parts = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=8,
)

# 密码：允许为空（None / 空串）或任意短字符串（需求 2.4 允许空密码保存）。
_passwords = st.one_of(st.none(), st.text(max_size=12))


@st.composite
def _valid_email(draw: st.DrawFn) -> str:
    """构造一定满足邮箱格式（恰好一个 @、本地名非空、域名非空且含点号）的邮箱。"""
    local = draw(_email_parts)
    domain = draw(_email_parts)
    return f"{local}@{domain}.com"


@st.composite
def _batch_plans(
    draw: st.DrawFn,
) -> tuple[list[CreateUserCommand], list[str], list[tuple[int, ErrorCode]]]:
    """生成一个批量请求计划。

    Returns:
        三元组 ``(records, expected_created_accounts, expected_failures)``：

        * ``records``：传给 ``batch_create_users`` 的记录列表（长度 1..30）。
        * ``expected_created_accounts``：期望被创建的账号列表（有效且首次出现唯一）。
        * ``expected_failures``：期望的失败明细 ``(row_id=行索引, reason=错误码)``，
          按行索引升序排列（与服务逐条处理的追加顺序一致）。
    """
    n = draw(st.integers(min_value=1, max_value=_MAX_RECORDS))
    kinds = st.sampled_from(["valid", "missing", "bad_role", "bad_email", "dup"])

    records: list[CreateUserCommand] = []
    expected_created: list[str] = []
    expected_failures: list[tuple[int, ErrorCode]] = []
    valid_accounts: list[str] = []  # 此前已出现的有效账号（供 dup 复用）。
    valid_counter = 0
    inv_counter = 0

    for index in range(n):
        kind = draw(kinds)

        if kind == "valid":
            account = f"v{valid_counter}"
            valid_counter += 1
            records.append(
                CreateUserCommand(
                    role=draw(_roles),
                    account=account,
                    email=draw(_valid_email()),
                    password=draw(_passwords),
                )
            )
            # 全新唯一账号 -> 批次内首次出现 -> 必被创建。
            expected_created.append(account)
            valid_accounts.append(account)

        elif kind == "missing":
            # 账号空白 -> 必填缺失（角色仍为合法非空，以隔离缺失原因）。
            records.append(
                CreateUserCommand(
                    role=draw(_roles),
                    account=draw(_blank_accounts),
                    email=draw(_valid_email()),
                )
            )
            expected_failures.append((index, ErrorCode.MISSING_REQUIRED_FIELD))

        elif kind == "bad_role":
            account = f"x{inv_counter}"
            inv_counter += 1
            records.append(
                CreateUserCommand(
                    role=draw(_invalid_roles),
                    account=account,
                    email=draw(_valid_email()),
                )
            )
            expected_failures.append((index, ErrorCode.INVALID_ROLE))

        elif kind == "bad_email":
            account = f"x{inv_counter}"
            inv_counter += 1
            records.append(
                CreateUserCommand(
                    role=draw(_roles),
                    account=account,
                    email=draw(_invalid_emails),
                )
            )
            expected_failures.append((index, ErrorCode.INVALID_EMAIL_FORMAT))

        else:  # kind == "dup"
            if valid_accounts:
                # 复用此前已出现的有效账号 -> 批次内重复 -> DUPLICATE_ACCOUNT。
                records.append(
                    CreateUserCommand(
                        role=draw(_roles),
                        account=draw(st.sampled_from(valid_accounts)),
                        email=draw(_valid_email()),
                    )
                )
                expected_failures.append((index, ErrorCode.DUPLICATE_ACCOUNT))
            else:
                # 尚无可复用的有效账号 -> 退化为一条邮箱非法的无效记录，保证分类确定。
                account = f"x{inv_counter}"
                inv_counter += 1
                records.append(
                    CreateUserCommand(
                        role=draw(_roles),
                        account=account,
                        email=draw(_invalid_emails),
                    )
                )
                expected_failures.append((index, ErrorCode.INVALID_EMAIL_FORMAT))

    return records, expected_created, expected_failures


@pytest.mark.property
@settings(max_examples=100)
@given(plan=_batch_plans())
def test_batch_create_processes_all_valid_records(
    plan: tuple[list[CreateUserCommand], list[str], list[tuple[int, ErrorCode]]],
) -> None:
    """批量创建：全部有效记录被创建，无效记录被跳过并在失败明细中报告。"""
    records, expected_created, expected_failures = plan

    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)
        service = UserService(repo)

        result = service.batch_create_users(records)

        # 1) 记录数落在 1..1000 -> 逐条处理而非整体拒绝。
        assert result.error_code is None, (
            f"1..1000 条记录应逐条处理，不应整体拒绝，但得到 {result.error_code}"
        )

        # 2) 全部有效且首次出现唯一的记录都被创建。
        assert result.success_count == len(expected_created), (
            f"成功数应等于期望创建数 {len(expected_created)}，"
            f"实得 {result.success_count}"
        )
        for account in expected_created:
            assert repo.get_user_by_account(account) is not None, (
                f"有效记录账号 {account!r} 应已被创建，但系统内查无此账号"
            )

        # 3) 无效/重复记录数与失败明细（行标识 + 原因）与构造时完全一致。
        assert result.failure_count == len(expected_failures), (
            f"失败数应等于无效/重复记录数 {len(expected_failures)}，"
            f"实得 {result.failure_count}"
        )
        actual_failures = [(f.row_id, f.reason) for f in result.failures]
        assert actual_failures == expected_failures, (
            "失败明细（行标识与原因）应与构造时一致；"
            f"期望 {expected_failures}，实得 {actual_failures}"
        )

        # 3b) 无效记录（专属 x* 账号）未被创建。
        invalid_accounts = {
            rec.account
            for idx, rec in enumerate(records)
            if str(rec.account).startswith("x")
            and idx in {row_id for row_id, _ in expected_failures}
        }
        for account in invalid_accounts:
            assert repo.get_user_by_account(account) is None, (
                f"无效记录账号 {account!r} 不应被创建"
            )

        # 4) 计数守恒（局部体现）：成功 + 失败 == 记录总数。
        assert result.success_count + result.failure_count == len(records)
    finally:
        session.close()
        engine.dispose()
