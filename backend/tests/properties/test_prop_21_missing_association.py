# Feature: homework-upload-system, Property 21: 关联实体不存在则拒绝
"""Property 21：关联实体不存在则拒绝。

依据 design.md「Correctness Properties」Property 21：

    *For any* 创建课程时不存在的 ``class_id``，或创建作业时不存在的
    ``course_id``，创建应被拒绝、不产生任何记录，并分别返回“班级不存在错误”
    或“课程不存在错误”。

**Validates: Requirements 7.5, 8.12**

测试策略：

本属性覆盖两条创建路径，分别用两个属性测试验证：

1. **课程创建**（需求 7.5）：在一套空的内存数据库（无任何班级）上，使用任意
   非空白的 ``class_id`` 调用
   :meth:`app.services.course_service.CourseService.create_course`。由于该
   ``class_id`` 必然不存在，结果应为失败、错误码为
   :attr:`ErrorCode.CLASS_NOT_FOUND`，且 ``list_courses()`` 仍为空（不产生任何
   课程记录）。为隔离“班级存在性”这一被测分支，其余输入（``semester`` /
   ``name``）均生成为合法值（非空白、``name`` 长度 1..20），使校验在班级存在性
   处短路。

2. **作业创建**（需求 8.12）：在一套空的内存数据库（无任何课程）上，使用任意
   非空白的 ``course_id`` 调用
   :meth:`app.services.assignment_service.AssignmentService.create_assignment`。
   由于该 ``course_id`` 必然不存在，结果应为失败、错误码为
   :attr:`ErrorCode.COURSE_NOT_FOUND`，且不产生任何作业记录。

   ``create_assignment`` 的校验顺序为：角色 -> 必填 -> 长度 -> 扩展名 ->
   最大大小 -> 课程存在性 -> 截止时间。课程存在性在截止时间之前判定，因此本
   测试需保证除 ``course_id`` 外的所有输入均合法（合法标题、非空且为
   :data:`ALLOWED_EXTENSIONS` 子集的扩展名集合、合法或缺省的最大大小、晚于
   ``now`` 的截止时间），从而确保触发的恰是 ``COURSE_NOT_FOUND`` 分支。

为保证 Hypothesis 各用例之间 DB 状态互相隔离，测试体内部每次都构造一套全新的
内存引擎 + 会话 + 仓储（``create_db_engine`` -> ``create_all`` ->
``create_session_factory`` -> ``Repository(session)``），其中不含任何班级/课程，
因此任意标识都属于“不存在”。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.core.errors import ErrorCode
from app.core.validators import ALLOWED_EXTENSIONS
from app.db import create_all, create_db_engine, create_session_factory
from app.models import Assignment, Course
from app.repository import Repository
from app.services.assignment_service import (
    AssignmentService,
    CreateAssignmentCommand,
)
from app.services.course_service import CourseService

# 固定的“当前时间”，使截止时间校验具有确定性（与时钟无关）。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 非空白、长度 1..20 的标识/字段值：从可见 ASCII（码点 33..126，不含空白）取字符，
# 保证 validate_required 通过，且长度落在常见字段上限（如课程名 1..20）内。
_non_blank_text = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 学期：非空白即可（长度上限较宽松），复用非空白文本生成器。
_semesters = _non_blank_text

# 允许扩展名集合：ALLOWED_EXTENSIONS 的非空子集，保证扩展名集合校验通过，
# 从而让校验在“课程存在性”处短路（而非更早的扩展名校验）。
_allowed_ext_sets = st.sets(
    st.sampled_from(sorted(ALLOWED_EXTENSIONS)),
    min_size=1,
    max_size=len(ALLOWED_EXTENSIONS),
)

# 最大文件大小：None（缺省 -> 5MB）或合法整数 1..100，二者皆能通过取值校验。
_max_file_sizes = st.one_of(st.none(), st.integers(min_value=1, max_value=100))


@pytest.mark.property
@settings(max_examples=100)
@given(
    class_id=_non_blank_text,
    semester=_semesters,
    name=_non_blank_text,
)
def test_create_course_rejected_when_class_missing(
    class_id: str, semester: str, name: str
) -> None:
    """不存在的 class_id 创建课程应被拒绝（CLASS_NOT_FOUND）且不产生任何课程记录。"""
    engine = create_db_engine()  # 全新内存 SQLite，零班级零课程
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 系统中无任何班级，故任意 class_id 均“不存在”（需求 7.5）。
        result = CourseService(repo).create_course(
            current_role="Teacher",
            semester=semester,
            name=name,
            class_id=class_id,
        )

        # 创建被拒绝并返回“班级不存在错误”。
        assert result.ok is False
        assert result.error_code == ErrorCode.CLASS_NOT_FOUND
        assert result.course_id is None

        # 不产生任何课程记录：下拉列表与底层表均为空。
        assert repo.list_courses() == []
        course_count = repo.session.scalar(select(func.count()).select_from(Course))
        assert course_count == 0
    finally:
        session.close()
        engine.dispose()


@pytest.mark.property
@settings(max_examples=100)
@given(
    course_id=_non_blank_text,
    title=_non_blank_text,
    allowed_extensions=_allowed_ext_sets,
    max_file_size_mb=_max_file_sizes,
)
def test_create_assignment_rejected_when_course_missing(
    course_id: str,
    title: str,
    allowed_extensions: set[str],
    max_file_size_mb: int | None,
) -> None:
    """不存在的 course_id 创建作业应被拒绝（COURSE_NOT_FOUND）且不产生任何作业记录。"""
    engine = create_db_engine()  # 全新内存 SQLite，零课程零作业
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 截止时间晚于固定 now，确保课程存在性校验先于截止时间校验触发（需求 8.12）。
        cmd = CreateAssignmentCommand(
            title=title,
            content="",
            course_id=course_id,
            allowed_extensions=allowed_extensions,
            max_file_size_mb=max_file_size_mb,
            deadline=_NOW + timedelta(days=1),
        )

        # 系统中无任何课程，故任意 course_id 均“不存在”。
        result = AssignmentService(repo).create_assignment(
            current_role="Teacher",
            cmd=cmd,
            now=_NOW,
        )

        # 创建被拒绝并返回“课程不存在错误”。
        assert result.ok is False
        assert result.error_code == ErrorCode.COURSE_NOT_FOUND
        assert result.assignment_id is None

        # 不产生任何作业记录。
        assignment_count = repo.session.scalar(
            select(func.count()).select_from(Assignment)
        )
        assert assignment_count == 0
    finally:
        session.close()
        engine.dispose()
