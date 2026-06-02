"""AssignmentService 的示例 / 边界单元测试（task 10.3）。

与属性测试（tests/properties/）互补：本文件以**具体示例**覆盖
:class:`app.services.assignment_service.AssignmentService` 中两类与下拉数据/默认值
相关的行为：

1. ``list_courses`` 作为下拉数据来源，应返回库中现存课程集合（需求 8.4）。
2. ``create_assignment`` 未指定最大文件大小时，应默认归一化为 5MB（需求 8.10）；
   显式指定合法值时则保留该值。

来源依据：
- 需求 8.4（下拉提供已存在课程列表）。
- 需求 8.10（未指定最大文件大小 -> 默认 5MB）。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.assignment_service import (
    AssignmentService,
    CreateAssignmentCommand,
)

# 统一的确定性时间基准；deadline 严格晚于 now（需求 8.13）。
NOW = datetime(2024, 1, 1, 12, 0, 0)
FUTURE_DEADLINE = NOW + timedelta(days=1)


@pytest.fixture()
def repository() -> Repository:
    """提供绑定到内存 SQLite 的 Repository（每个测试独立建表）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    return Repository(session)


def _create_course(
    repository: Repository,
    *,
    semester: str,
    name: str,
    teacher_account: str,
) -> str:
    """在库中创建 Teacher -> Class -> Course，返回新建课程标识。

    每个课程都需要一个班级，每个班级都需要一名教师；账号需唯一，故由调用方
    通过 ``teacher_account`` 保证不重复。
    """
    with repository.transaction():
        teacher = repository.create_user(role="Teacher", account=teacher_account)
        clazz = repository.create_class(
            school="清华大学",
            grade="2024级",
            major="计算机科学",
            teacher_id=teacher.id,
        )
        course = repository.create_course(
            semester=semester,
            name=name,
            class_id=clazz.id,
        )
    return course.id


# --------------------------------------------------------------------------- #
# 下拉数据来源：list_courses（需求 8.4）                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_list_courses_empty_returns_empty_list(repository: Repository) -> None:
    """库中无课程时，list_courses 返回空列表。"""
    service = AssignmentService(repository)
    assert service.list_courses() == []


@pytest.mark.unit
def test_list_courses_returns_existing_courses(repository: Repository) -> None:
    """创建 N 门课程后，list_courses 应恰好返回这 N 门课程。

    断言：返回的课程 id 集合与已创建的一致；且每个返回项的 name/semester
    与持久化值一致。
    """
    expected = {
        _create_course(
            repository, semester="2024秋", name="软件工程", teacher_account="t-001"
        ): ("软件工程", "2024秋"),
        _create_course(
            repository, semester="2024春", name="数据结构", teacher_account="t-002"
        ): ("数据结构", "2024春"),
        _create_course(
            repository, semester="2025秋", name="操作系统", teacher_account="t-003"
        ): ("操作系统", "2025秋"),
    }

    service = AssignmentService(repository)
    summaries = service.list_courses()

    # 数量与 id 集合完全匹配。
    assert len(summaries) == len(expected)
    assert {s.id for s in summaries} == set(expected)

    # 每个返回项的 name/semester 与持久化值一致，label 含名称与学期。
    for summary in summaries:
        expected_name, expected_semester = expected[summary.id]
        assert summary.name == expected_name
        assert summary.semester == expected_semester
        assert expected_name in summary.label
        assert expected_semester in summary.label


# --------------------------------------------------------------------------- #
# 最大文件大小默认值（需求 8.10）                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_create_assignment_default_max_file_size_is_5mb(repository: Repository) -> None:
    """未指定 max_file_size_mb 时，持久化的作业最大大小应默认为 5MB。"""
    course_id = _create_course(
        repository, semester="2024秋", name="软件工程", teacher_account="t-001"
    )
    service = AssignmentService(repository)

    result = service.create_assignment(
        "Teacher",
        CreateAssignmentCommand(
            title="第一次作业",
            content="请提交实验报告",
            course_id=course_id,
            allowed_extensions={"pdf"},
            max_file_size_mb=None,  # 未指定 -> 默认 5MB
            deadline=FUTURE_DEADLINE,
        ),
        NOW,
    )

    assert result.ok is True
    assert result.error_code is None
    assert result.assignment_id is not None

    stored = repository.get_assignment(result.assignment_id)
    assert stored is not None
    assert stored.max_file_size_mb == 5


@pytest.mark.unit
def test_create_assignment_explicit_max_file_size_is_preserved(
    repository: Repository,
) -> None:
    """显式指定合法 max_file_size_mb（10）时应原样持久化。"""
    course_id = _create_course(
        repository, semester="2024秋", name="软件工程", teacher_account="t-001"
    )
    service = AssignmentService(repository)

    result = service.create_assignment(
        "Teacher",
        CreateAssignmentCommand(
            title="第二次作业",
            content="提交源码压缩包",
            course_id=course_id,
            allowed_extensions=["zip"],
            max_file_size_mb=10,
            deadline=FUTURE_DEADLINE,
        ),
        NOW,
    )

    assert result.ok is True
    assert result.assignment_id is not None

    stored = repository.get_assignment(result.assignment_id)
    assert stored is not None
    assert stored.max_file_size_mb == 10
