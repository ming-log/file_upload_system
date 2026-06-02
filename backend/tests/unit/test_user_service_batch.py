"""UserService 批量处理的示例 / 边界单元测试（任务 7.13）。

聚焦需求 3.4（批量创建请求不含任何记录 -> 记录为空错误）以及需求 3.2 / 6.6
（逐条失败记录的「行标识 + 失败原因」明细）。与属性测试（任务 7.10–7.12）互补：
本文件以**具体示例**精确断言 :class:`~app.services.user_service.BatchResult` 的
``error_code`` / ``success_count`` / ``failure_count`` 以及 ``failures`` 列表中
每条 :class:`~app.services.user_service.BatchFailure` 的 ``row_id`` 与 ``reason``。

覆盖范围：

* **空批次整体拒绝**（需求 3.4）：``batch_create_users([])`` 与
  ``batch_import_students(...)`` 空记录均返回 ``EMPTY_BATCH`` 且零计数。
* **单条失败明细**（需求 3.2）：一条有效 + 一条邮箱格式非法 -> 成功 1、失败 1，
  失败明细的 ``row_id`` 为该非法记录的 0 基行索引，``reason`` 为
  ``INVALID_EMAIL_FORMAT``。
* **批次内账号重复**（需求 3.2）：两条同账号记录 -> 首条成功、次条
  ``DUPLICATE_ACCOUNT`` 失败，``row_id == 1``。
* **学生批量导入失败明细**（需求 6.6）：必填缺失（姓名空白）-> 失败明细
  ``row_id == student_id``、``reason == MISSING_REQUIRED_FIELD``；批次内学号重复
  -> ``DUPLICATE_STUDENT_ID`` 失败、``row_id == student_id``。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import (
    BatchResult,
    StudentRecord,
    UserRecord,
    UserService,
)


@pytest.fixture()
def repo() -> Iterator[Repository]:
    """提供绑定到独立内存 SQLite 的 Repository（每个测试隔离）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield Repository(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def service(repo: Repository) -> UserService:
    """基于隔离仓储构造 UserService。"""
    return UserService(repo)


@pytest.fixture()
def class_id(repo: Repository) -> str:
    """创建一名 Teacher 与一个真实班级，返回其班级标识。

    ``batch_import_students`` 不校验班级是否存在，但 ``User.class_id`` 是指向
    ``classes.id`` 的非空外键，故成功创建学生需要一个真实存在的班级。
    """
    with repo.transaction():
        teacher = repo.create_user(role="Teacher", account="teacher-fixture-account")
        clazz = repo.create_class(
            school="S", grade="G", major="M", teacher_id=teacher.id
        )
        return clazz.id


# --------------------------------------------------------------------------- #
# 1) 空批次整体拒绝（需求 3.4）                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_batch_create_users_empty_rejected(service: UserService) -> None:
    """空记录批量创建应整体拒绝并返回 EMPTY_BATCH，零计数（需求 3.4）。"""
    result = service.batch_create_users([])

    assert isinstance(result, BatchResult)
    assert result.error_code is ErrorCode.EMPTY_BATCH
    assert result.success_count == 0
    assert result.failure_count == 0
    assert result.failures == []


@pytest.mark.unit
def test_batch_import_students_empty_rejected(
    service: UserService, class_id: str
) -> None:
    """空记录批量导入学生应整体拒绝并返回 EMPTY_BATCH，零计数（需求 3.4 语义）。"""
    result = service.batch_import_students("Teacher", class_id, [])

    assert result.error_code is ErrorCode.EMPTY_BATCH
    assert result.success_count == 0
    assert result.failure_count == 0
    assert result.failures == []


# --------------------------------------------------------------------------- #
# 2) 单条失败明细：行标识 + 失败原因（需求 3.2）                                #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_batch_create_users_single_invalid_email_failure_detail(
    service: UserService, repo: Repository
) -> None:
    """一条有效 + 一条非法邮箱：成功 1、失败 1，失败明细精确（需求 3.2）。

    无效记录位于索引 1，故其 ``row_id`` 应为 1，``reason`` 为 INVALID_EMAIL_FORMAT。
    """
    records = [
        UserRecord(role="Teacher", account="valid-acc", email="ok@example.com"),
        UserRecord(role="Student", account="bad-acc", email="not-an-email"),
    ]

    result = service.batch_create_users(records)

    assert result.error_code is None  # 逐条处理，而非整体拒绝
    assert result.success_count == 1
    assert result.failure_count == 1
    assert len(result.failures) == 1

    failure = result.failures[0]
    assert failure.row_id == 1
    assert failure.reason is ErrorCode.INVALID_EMAIL_FORMAT

    # 有效记录确已创建；无效记录未创建。
    assert repo.get_user_by_account("valid-acc") is not None
    assert repo.get_user_by_account("bad-acc") is None


# --------------------------------------------------------------------------- #
# 3) 批次内账号重复（需求 3.2）                                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_batch_create_users_duplicate_account_within_batch(
    service: UserService,
) -> None:
    """同账号出现两次：首条成功、次条 DUPLICATE_ACCOUNT 失败，row_id == 1。"""
    records = [
        UserRecord(role="Teacher", account="dup", email="first@example.com"),
        UserRecord(role="Student", account="dup", email="second@example.com"),
    ]

    result = service.batch_create_users(records)

    assert result.error_code is None
    assert result.success_count == 1
    assert result.failure_count == 1
    assert len(result.failures) == 1

    failure = result.failures[0]
    assert failure.row_id == 1
    assert failure.reason is ErrorCode.DUPLICATE_ACCOUNT


# --------------------------------------------------------------------------- #
# 4) 学生批量导入失败明细：row_id == student_id（需求 6.6）                     #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_batch_import_students_missing_field_failure_detail(
    service: UserService, class_id: str
) -> None:
    """学生记录姓名空白 -> 失败明细 row_id 为学号、reason 为 MISSING_REQUIRED_FIELD。"""
    records = [
        StudentRecord(student_id="S001", name="Alice", email="alice@example.com"),
        StudentRecord(student_id="S002", name="   ", email="bob@example.com"),
    ]

    result = service.batch_import_students("Teacher", class_id, records)

    assert result.error_code is None
    assert result.success_count == 1
    assert result.failure_count == 1
    assert len(result.failures) == 1

    failure = result.failures[0]
    assert failure.row_id == "S002"  # 学生批量失败行标识使用学号（需求 6.6）
    assert failure.reason is ErrorCode.MISSING_REQUIRED_FIELD


@pytest.mark.unit
def test_batch_import_students_duplicate_student_id_within_batch(
    service: UserService, class_id: str
) -> None:
    """批次内学号重复 -> 次条 DUPLICATE_STUDENT_ID 失败，row_id 为学号（需求 6.6）。"""
    records = [
        StudentRecord(student_id="DUP01", name="Alice", email="alice@example.com"),
        StudentRecord(student_id="DUP01", name="Bob", email="bob@example.com"),
    ]

    result = service.batch_import_students("Teacher", class_id, records)

    assert result.error_code is None
    assert result.success_count == 1
    assert result.failure_count == 1
    assert len(result.failures) == 1

    failure = result.failures[0]
    assert failure.row_id == "DUP01"
    assert failure.reason is ErrorCode.DUPLICATE_STUDENT_ID
