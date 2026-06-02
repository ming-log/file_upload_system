# Feature: homework-upload-system, Property 14: 班级合法输入创建成功
"""Property 14：班级合法输入创建成功。

依据 design.md「Correctness Properties」Property 14：

    *For any* school/grade/major 均非空白且长度均为 1..20 的输入，班级创建应成功
    并返回非空班级标识。

**Validates: Requirements 5.8**

测试策略：
对任意「school / grade / major 三者均非空白且字符长度均为 1..20」的合法输入，
由一名 ``Teacher`` 调用 :meth:`app.services.class_service.ClassService.create_class`
应成功（``result.ok is True``、``result.error_code is None``），并返回一个非空字符串
班级标识（``result.class_id``）。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的
内存引擎 + 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``）。由于 ``Class.teacher_id`` 是非空外键，先创建一名
``Teacher`` 用户作为 ``teacher_id`` 使用。

输入生成说明：``validate_required`` 将纯空白视为“缺失”，``validate_length`` 以字符数
计长。为确保归一化后仍满足「非空白且长度 1..20」，本测试直接从可见的非空白
ASCII 字符（码点 33..126）构造长度 1..20 的字符串，从而天然满足约束。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.class_service import ClassService

# 非空白、长度 1..20 的字段值：从可见 ASCII（码点 33..126，不含空白）取字符，
# 保证 validate_required 通过且字符长度恒为 1..20（覆盖 Property 14 输入空间）。
_class_fields = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 教师账号：非空、非纯空白字符串（满足 validate_required，需求 2.6）。
_teacher_accounts = (
    st.text(min_size=1, max_size=32).map(lambda s: s.strip()).filter(lambda s: s != "")
)


@pytest.mark.property
@settings(max_examples=100)
@given(
    school=_class_fields,
    grade=_class_fields,
    major=_class_fields,
    teacher_account=_teacher_accounts,
)
def test_class_creation_succeeds_for_valid_input(
    school: str, grade: str, major: str, teacher_account: str
) -> None:
    """合法 school/grade/major（非空白、长度 1..20）的班级创建应成功并返回非空标识。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # Class.teacher_id 为非空外键：先创建一名 Teacher 用户作为 teacher_id。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=teacher_account)

        result = ClassService(repo).create_class(
            "Teacher", school, grade, major, teacher_id=teacher.id
        )

        # 需求 5.8：合法输入创建成功并返回非空班级标识。
        assert result.ok is True, f"班级创建失败：error_code={result.error_code}"
        assert result.error_code is None
        assert isinstance(result.class_id, str)
        assert result.class_id != ""
    finally:
        session.close()
        engine.dispose()
