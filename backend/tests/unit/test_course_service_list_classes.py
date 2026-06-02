"""CourseService.list_classes 的示例单元测试（task 9.3，下拉数据来源）。

与 task 9.1 的实现互补：本文件以**具体示例**断言
:meth:`app.services.course_service.CourseService.list_classes` 返回供前端下拉
选择的「现存班级集合」（需求 7.3）。

来源依据：
- 需求 7.3：创建课程时通过下拉选择提供已存在的班级列表供教师选择关联班级。

设计要点：
- ``list_classes`` 将 :meth:`Repository.list_classes` 返回的 ORM 班级映射为
  :class:`~app.services.course_service.ClassSummary`，仅暴露下拉所需的最小字段
  （``id`` / ``school`` / ``grade`` / ``major``）及展示标签 ``label``。
- 班级集合无固定顺序，因此断言以「集合」语义（按 ``id`` 比较）进行，避免对
  返回顺序作出过强假设。
"""

from __future__ import annotations

import pytest

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.course_service import ClassSummary, CourseService


@pytest.fixture()
def repository() -> Repository:
    """提供绑定到内存 SQLite 的 Repository（每个测试独立建表）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    return Repository(session)


@pytest.fixture()
def teacher_id(repository: Repository) -> str:
    """在库中创建一名 Teacher 并返回其用户标识（用作 Class.teacher_id 外键）。"""
    with repository.transaction():
        teacher = repository.create_user(role="Teacher", account="t-001")
    return teacher.id


# --------------------------------------------------------------------------- #
# 空集合：无班级时返回空列表（需求 7.3）                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_list_classes_empty_when_no_classes(repository: Repository) -> None:
    """系统中没有任何班级时，list_classes 应返回空列表。"""
    service = CourseService(repository)

    result = service.list_classes()

    assert result == []


# --------------------------------------------------------------------------- #
# 非空集合：返回现存班级集合（需求 7.3）                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_list_classes_returns_existing_class_set(
    repository: Repository, teacher_id: str
) -> None:
    """创建 N 个班级后，list_classes 应恰好返回这 N 个班级，且字段正确映射。"""
    # 准备：创建 3 个班级，记录其 id 与字段值。
    specs = [
        ("清华大学", "2024级", "计算机科学"),
        ("北京大学", "2023级", "软件工程"),
        ("浙江大学", "2025级", "人工智能"),
    ]
    created: dict[str, tuple[str, str, str]] = {}
    with repository.transaction():
        for school, grade, major in specs:
            clazz = repository.create_class(
                school=school, grade=grade, major=major, teacher_id=teacher_id
            )
            created[clazz.id] = (school, grade, major)

    service = CourseService(repository)
    summaries = service.list_classes()

    # 返回项均为 ClassSummary。
    assert all(isinstance(s, ClassSummary) for s in summaries)

    # 数量一致，且 id 集合与现存班级 id 集合完全一致（集合语义，忽略顺序）。
    assert len(summaries) == len(created)
    assert {s.id for s in summaries} == set(created)

    # 每个摘要的 school/grade/major 字段与对应班级一致。
    by_id = {s.id: s for s in summaries}
    for class_id, (school, grade, major) in created.items():
        summary = by_id[class_id]
        assert summary.school == school
        assert summary.grade == grade
        assert summary.major == major
        # label 属性格式为 "学校 年级 专业"。
        assert summary.label == f"{school} {grade} {major}"


# --------------------------------------------------------------------------- #
# 单个班级：精确反映新建班级（需求 7.3）                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_list_classes_reflects_single_created_class(
    repository: Repository, teacher_id: str
) -> None:
    """新建一个班级后，list_classes 应返回恰好一项且字段与之匹配。"""
    with repository.transaction():
        clazz = repository.create_class(
            school="复旦大学", grade="2024级", major="数据科学", teacher_id=teacher_id
        )

    summaries = CourseService(repository).list_classes()

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == clazz.id
    assert summary.school == "复旦大学"
    assert summary.grade == "2024级"
    assert summary.major == "数据科学"
    assert summary.label == "复旦大学 2024级 数据科学"
