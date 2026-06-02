# Feature: homework-upload-system, Property 22: 课程合法输入创建成功并正确关联
"""Property 22：课程合法输入创建成功并正确关联。

依据 design.md「Correctness Properties」Property 22：

    *For any* semester/name 非空白、name 长度 1..20 且关联班级存在的输入，课程创建
    应成功、``class_id`` 等于所选班级，并返回非空课程标识。

**Validates: Requirements 7.7**

测试策略：
对任意「semester / name 均非空白且字符长度均为 1..20」的合法输入，并选择一个
**已存在** 的班级作为 ``class_id``，由一名 ``Teacher`` 调用
:meth:`app.services.course_service.CourseService.create_course` 应成功
（``result.ok is True``、``result.error_code is None``），返回非空字符串课程标识，
且持久化后的课程其 ``class_id`` 等于所选班级标识（需求 7.7 关联约束）。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的
内存引擎 + 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``）。``Course.class_id`` 是非空外键，``Class.teacher_id``
亦为非空外键，故先创建一名 ``Teacher`` 用户，再创建一个班级作为已存在的关联班级。

输入生成说明：``validate_required`` 将纯空白视为「缺失」，``validate_length`` 以字符数
计长。为确保归一化后仍满足「非空白且长度 1..20」，本测试直接从可见的非空白
ASCII 字符（码点 33..126）构造长度 1..20 的字符串，从而天然满足约束。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.course_service import CourseService

# 非空白、长度 1..20 的字段值：从可见 ASCII（码点 33..126，不含空白）取字符，
# 保证 validate_required 通过且字符长度恒为 1..20（覆盖 Property 22 输入空间）。
_non_blank_1_20 = st.text(
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
    semester=_non_blank_1_20,
    name=_non_blank_1_20,
    teacher_account=_teacher_accounts,
)
def test_course_creation_succeeds_and_associates_class(
    semester: str, name: str, teacher_account: str
) -> None:
    """合法 semester/name 与已存在班级 -> 创建成功、返回非空标识且 class_id 正确关联。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # Course.class_id 须指向已存在班级；Class.teacher_id 为非空外键。
        # 先建一名 Teacher，再建一个班级作为关联目标。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=teacher_account)
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            class_id = clazz.id

        result = CourseService(repo).create_course("Teacher", semester, name, class_id)

        # 需求 7.7：合法输入创建成功并返回非空课程标识。
        assert result.ok is True, f"课程创建失败：error_code={result.error_code}"
        assert result.error_code is None
        assert isinstance(result.course_id, str)
        assert result.course_id != ""

        # 需求 7.7：持久化的课程确实存在，且关联到所选班级。
        course = repo.get_course(result.course_id)
        assert course is not None
        assert course.class_id == class_id
    finally:
        session.close()
        engine.dispose()
