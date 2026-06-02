# Feature: homework-upload-system, Property 15: 学生缺省密码赋值
"""Property 15：学生缺省密码赋值。

依据 design.md「Correctness Properties」Property 15：

    *For any* 学生创建记录，若未提供密码则存储密码应等于默认密码 ``"minglog666"``，
    若提供了密码则保留所提供的值。

**Validates: Requirements 6.3**

测试策略：

对任意学生创建记录（学号/姓名/邮箱均合法），密码取自
``{None, "", "  ", 任意非空白字符串}``：

* 当密码为 ``None`` 或纯空白（``validate_required`` 判为“缺失”）时，存储的
  ``User.password`` 应等于 :data:`~app.core.validators.DEFAULT_PASSWORD`
  （``"minglog666"``）；
* 当密码为非空白字符串时，存储的 ``User.password`` 应原样保留所提供的值。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的
内存引擎 + 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``）。由于 :meth:`UserService.create_student` 会将学生
关联到 ``class_id``（``User.class_id`` 为外键），测试先创建一名 ``Teacher`` 用户，
再以其为 ``teacher_id`` 创建一个真实班级，使用该班级 id 作为 ``class_id``，从而
避免外键约束失败。

账号约定（重要）：依据 :meth:`UserService.create_student` 的实现，学生以
``account == student_id`` 作为登录账号。因此创建后通过
``repo.get_user_by_account(student_id)`` 即可取回该学生用户并检查 ``.password``。
"""

from __future__ import annotations

from typing import Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.validators import DEFAULT_PASSWORD, validate_required
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import StudentRecord, UserService

# 学号 / 姓名：非空白、可打印 ASCII（码点 33..126），保证 validate_required 通过，
# 长度落在模型存储宽度内。
_student_ids = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)
_names = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 邮箱片段：仅小写字母，用于拼出一定合法的邮箱 local@domain.com（通过 validate_email）。
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


# 密码：覆盖 {None, 空串, 纯空白, 任意非空白字符串}，以同时探查“缺省赋默认密码”
# 与“保留所提供密码”两条分支。
_passwords = st.one_of(
    st.none(),
    st.just(""),
    st.just("  "),
    st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1,
        max_size=16,
    ),
)


@pytest.mark.property
@settings(max_examples=100)
@given(
    student_id=_student_ids,
    name=_names,
    email=_valid_emails(),
    password=_passwords,
)
def test_student_default_password_assignment(
    student_id: str,
    name: str,
    email: str,
    password: Optional[str],
) -> None:
    """未提供（None/空白）密码时存默认密码；提供非空白密码时原样保留（需求 6.3）。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 学生将关联到 class_id（User.class_id 外键）：先建 Teacher，再建真实班级，
        # 用其 id 作为 class_id，避免外键约束失败。教师账号由学号派生并加前缀，
        # 其长度恒大于学号，故必不与学生账号（account == student_id）发生唯一性冲突。
        teacher_account = "teacher_" + student_id
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=teacher_account)
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
        class_id = clazz.id

        result = UserService(repo).create_student(
            "Teacher",
            class_id,
            StudentRecord(
                student_id=student_id, name=name, email=email, password=password
            ),
        )

        # 学号/姓名/邮箱均合法，创建应成功（隔离“密码缺省”这一被测属性）。
        assert result.ok is True, f"学生创建应成功，但得到 {result.error_code}"

        # 期望存储密码：None/空白 -> 默认密码；非空白 -> 原值。
        expected = password if validate_required(password) else DEFAULT_PASSWORD

        # 学生以 account == student_id 登录，故按账号取回该用户。
        stored = repo.get_user_by_account(student_id)
        assert stored is not None, "应能按 account==student_id 取回新建学生"
        assert stored.password == expected
    finally:
        session.close()
        engine.dispose()
