"""ORM 模型结构冒烟测试（task 4.3）。

通过 SQLAlchemy 反射断言五张核心表的必备字段、唯一约束与外键关系存在，
并验证 ``create_all`` 能在内存 SQLite 上创建全部表。这是结构级（smoke）
校验，不涉及业务逻辑或数据流。

对应需求：
* 2.1 —— User.account 系统内唯一；用户模型必备字段。
* 5.3 —— Class 必备字段与 teacher_id 外键。
* 6.2 —— User.student_id 唯一、class_id 外键。
* 7.2 —— Course 必备字段与 class_id 外键。
* 8.3 —— Assignment 必备字段与 course_id 外键。
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app.db import create_all, create_db_engine
from app.models import Assignment, Class, Course, Submission, User


def _column_names(model: type) -> set[str]:
    """返回模型映射表的列名集合。"""
    return set(model.__table__.columns.keys())


def _foreign_key_pairs(model: type) -> set[tuple[str, str]]:
    """返回 (本地列名, 目标 "表.列") 形式的外键对集合。"""
    pairs: set[tuple[str, str]] = set()
    for column in model.__table__.columns:
        for fk in column.foreign_keys:
            pairs.add((column.name, fk.target_fullname))
    return pairs


def _unique_column_names(model: type) -> set[str]:
    """收集模型上以唯一约束（单列）声明的列名。

    同时考虑列级 ``unique=True`` 与表级 :class:`UniqueConstraint`。
    """
    unique: set[str] = set()
    # 列级 unique=True。
    for column in model.__table__.columns:
        if column.unique:
            unique.add(column.name)
    # 表级 UniqueConstraint。
    from sqlalchemy import UniqueConstraint

    for constraint in model.__table__.constraints:
        if isinstance(constraint, UniqueConstraint):
            for column in constraint.columns:
                unique.add(column.name)
    return unique


# ---------------------------------------------------------------------------
# 必备字段（columns）存在性
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_user_has_required_columns() -> None:
    """User 模型包含全部必备字段（需求 2.1 / 6.2）。"""
    expected = {
        "id",
        "role",
        "account",
        "email",
        "password",
        "student_id",
        "name",
        "class_id",
    }
    assert expected <= _column_names(User)
    assert User.__tablename__ == "users"


@pytest.mark.unit
def test_class_has_required_columns() -> None:
    """Class 模型包含全部必备字段（需求 5.3）。"""
    expected = {"id", "school", "grade", "major", "teacher_id"}
    assert expected <= _column_names(Class)
    assert Class.__tablename__ == "classes"


@pytest.mark.unit
def test_course_has_required_columns() -> None:
    """Course 模型包含全部必备字段（需求 7.2）。"""
    expected = {"id", "semester", "name", "class_id"}
    assert expected <= _column_names(Course)
    assert Course.__tablename__ == "courses"


@pytest.mark.unit
def test_assignment_has_required_columns() -> None:
    """Assignment 模型包含全部必备字段（需求 8.3）。"""
    expected = {
        "id",
        "title",
        "content",
        "course_id",
        "allowed_extensions",
        "max_file_size_mb",
        "deadline",
    }
    assert expected <= _column_names(Assignment)
    assert Assignment.__tablename__ == "assignments"


@pytest.mark.unit
def test_submission_has_required_columns() -> None:
    """Submission 模型包含全部必备字段（需求 8.3 / 10.4）。"""
    expected = {
        "id",
        "student_id",
        "assignment_id",
        "file_name",
        "storage_id",
        "submitted_at",
    }
    assert expected <= _column_names(Submission)
    assert Submission.__tablename__ == "submissions"


# ---------------------------------------------------------------------------
# 唯一约束存在性
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unique_constraints_exist() -> None:
    """account / student_id / storage_id 存在唯一约束（需求 2.1 / 6.2 / 10.4）。"""
    user_unique = _unique_column_names(User)
    assert "account" in user_unique
    assert "student_id" in user_unique

    submission_unique = _unique_column_names(Submission)
    assert "storage_id" in submission_unique


# ---------------------------------------------------------------------------
# 外键关系存在性
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_foreign_keys_exist() -> None:
    """各模型的外键指向正确的目标表与列（需求 5.3 / 6.2 / 7.2 / 8.3 / 9.9）。"""
    assert ("class_id", "classes.id") in _foreign_key_pairs(User)
    assert ("teacher_id", "users.id") in _foreign_key_pairs(Class)
    assert ("class_id", "classes.id") in _foreign_key_pairs(Course)
    assert ("course_id", "courses.id") in _foreign_key_pairs(Assignment)

    submission_fks = _foreign_key_pairs(Submission)
    assert ("student_id", "users.id") in submission_fks
    assert ("assignment_id", "assignments.id") in submission_fks


# ---------------------------------------------------------------------------
# create_all 建表冒烟
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_all_creates_all_five_tables() -> None:
    """create_all 在内存 SQLite 上创建全部五张表。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)

    table_names = set(inspect(engine).get_table_names())
    expected_tables = {"users", "classes", "courses", "assignments", "submissions"}
    assert expected_tables <= table_names
