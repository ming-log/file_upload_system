"""ClassService.create_class 的示例 / 边界单元测试（task 8.1）。

与属性测试（task 8.2，tests/properties/）互补：本文件以**具体示例与边界值**
覆盖 :class:`app.services.class_service.ClassService` 的关键路径与错误分支。

校验顺序为：角色门控 -> 必填 -> 长度上限 -> 创建（需求 5.1-5.8）。

来源依据：
- 需求 5.1 / 5.2（Teacher 门控）-> FORBIDDEN
- 需求 5.7（school/grade/major 必填）-> MISSING_REQUIRED_FIELD
- 需求 5.4 / 5.5 / 5.6（各字段长度 ≤ 20，含字段名）-> FIELD_TOO_LONG
- 需求 5.8（合法输入创建成功并返回班级标识）
"""

from __future__ import annotations

import pytest

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.class_service import (
    CLASS_FIELD_MAX_LENGTH,
    ClassService,
    CreateClassResult,
)


@pytest.fixture()
def repository() -> Repository:
    """提供绑定到内存 SQLite 的 Repository（每个测试独立建表）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    return Repository(session)


@pytest.fixture()
def teacher_id(repository: Repository) -> str:
    """在库中创建一名 Teacher 并返回其用户标识（用作 Class.teacher_id）。"""
    with repository.transaction():
        teacher = repository.create_user(role="Teacher", account="t-001")
    return teacher.id


# --------------------------------------------------------------------------- #
# 角色门控（需求 5.1 / 5.2）                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role", ["Admin", "Student", "", "teacher"])
def test_create_class_non_teacher_forbidden(
    repository: Repository, teacher_id: str, role: str
) -> None:
    """非 Teacher 角色创建班级应被拒绝并返回 FORBIDDEN，且不创建任何班级。"""
    service = ClassService(repository)
    result = service.create_class(role, "清华大学", "2024", "计算机", teacher_id=teacher_id)

    assert result.ok is False
    assert result.error_code is ErrorCode.FORBIDDEN
    assert result.class_id is None
    # 未创建任何班级。
    assert repository.list_classes() == []


# --------------------------------------------------------------------------- #
# 必填字段（需求 5.7）                                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    ("school", "grade", "major"),
    [
        ("", "2024", "计算机"),       # school 空
        ("清华大学", "   ", "计算机"),  # grade 纯空白
        ("清华大学", "2024", ""),       # major 空
    ],
)
def test_create_class_missing_required_field(
    repository: Repository, teacher_id: str, school: str, grade: str, major: str
) -> None:
    """任一必填字段为空/纯空白应返回 MISSING_REQUIRED_FIELD，且不创建班级。"""
    service = ClassService(repository)
    result = service.create_class("Teacher", school, grade, major, teacher_id=teacher_id)

    assert result.ok is False
    assert result.error_code is ErrorCode.MISSING_REQUIRED_FIELD
    assert result.class_id is None
    assert repository.list_classes() == []


# --------------------------------------------------------------------------- #
# 字段长度上限（需求 5.4 / 5.5 / 5.6）                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("field", ["school", "grade", "major"])
def test_create_class_field_too_long(
    repository: Repository, teacher_id: str, field: str
) -> None:
    """某字段超过 20 字符应返回 FIELD_TOO_LONG 并标注该字段名，且不创建班级。"""
    values = {"school": "清华大学", "grade": "2024", "major": "计算机"}
    values[field] = "a" * (CLASS_FIELD_MAX_LENGTH + 1)

    service = ClassService(repository)
    result = service.create_class(
        "Teacher", values["school"], values["grade"], values["major"], teacher_id=teacher_id
    )

    assert result.ok is False
    assert result.error_code is ErrorCode.FIELD_TOO_LONG
    assert result.field == field
    assert result.class_id is None
    assert repository.list_classes() == []


@pytest.mark.unit
def test_create_class_field_at_limit_succeeds(
    repository: Repository, teacher_id: str
) -> None:
    """长度恰为上限（20）应通过长度校验并成功创建。"""
    at_limit = "a" * CLASS_FIELD_MAX_LENGTH
    service = ClassService(repository)
    result = service.create_class("Teacher", at_limit, at_limit, at_limit, teacher_id=teacher_id)

    assert result.ok is True
    assert result.error_code is None
    assert result.class_id is not None


# --------------------------------------------------------------------------- #
# 成功创建（需求 5.8）                                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_create_class_success_returns_class_id(
    repository: Repository, teacher_id: str
) -> None:
    """合法输入应成功创建班级、返回非空标识并正确持久化字段与 teacher_id。"""
    service = ClassService(repository)
    result = service.create_class("Teacher", "清华大学", "2024级", "计算机科学", teacher_id=teacher_id)

    assert result.ok is True
    assert result.error_code is None
    assert isinstance(result.class_id, str) and result.class_id

    # 已持久化且字段正确。
    classes = repository.list_classes()
    assert len(classes) == 1
    created = classes[0]
    assert created.id == result.class_id
    assert created.school == "清华大学"
    assert created.grade == "2024级"
    assert created.major == "计算机科学"
    assert created.teacher_id == teacher_id


# --------------------------------------------------------------------------- #
# 校验顺序：角色门控先于必填（需求 5.1 / 5.2 优先）                              #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_role_gate_precedes_required_check(repository: Repository) -> None:
    """即使必填字段也缺失，非 Teacher 仍应优先返回 FORBIDDEN。"""
    service = ClassService(repository)
    result = service.create_class("Student", "", "", "", teacher_id=None)

    assert result.ok is False
    assert result.error_code is ErrorCode.FORBIDDEN


@pytest.mark.unit
def test_create_class_result_constructors() -> None:
    """CreateClassResult 便捷构造器语义正确。"""
    success = CreateClassResult.success("cid-1")
    assert success.ok is True and success.class_id == "cid-1" and success.error_code is None

    failure = CreateClassResult.fail(ErrorCode.FIELD_TOO_LONG, field="school")
    assert failure.ok is False
    assert failure.class_id is None
    assert failure.error_code is ErrorCode.FIELD_TOO_LONG
    assert failure.field == "school"
