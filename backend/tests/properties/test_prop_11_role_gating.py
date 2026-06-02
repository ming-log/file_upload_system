# Feature: homework-upload-system, Property 11: 角色权限门控
"""Property 11：角色权限门控。

依据 design.md「Correctness Properties」Property 11：

    *For any* 受角色保护的操作（创建教师要求 Admin；创建班级/学生/课程/作业要求
    Teacher；提交作业要求 Student）与任意当前用户角色，仅当当前角色等于该操作
    所需角色时操作才被允许进入业务逻辑；否则返回"权限不足错误"且不产生任何记录。

**Validates: Requirements 4.2, 5.1, 5.2, 6.1, 6.8, 7.1, 8.1, 8.2, 9.1, 9.2**

测试策略：

本属性覆盖六条受角色保护的创建/提交路径，每条用一个独立的 ``@given`` 属性测试
验证，以保持清晰：

* ``UserService.create_teacher``     —— 要求 ``Admin``（需求 4.2）。
* ``ClassService.create_class``      —— 要求 ``Teacher``（需求 5.1 / 5.2）。
* ``UserService.create_student``     —— 要求 ``Teacher``（需求 6.1 / 6.8）。
* ``CourseService.create_course``    —— 要求 ``Teacher``（需求 7.1）。
* ``AssignmentService.create_assignment`` —— 要求 ``Teacher``（需求 8.1 / 8.2）。
* ``SubmissionService.submit``       —— 要求 ``Student``（需求 9.1 / 9.2）。

每个测试对当前角色 ``current_role`` 在 ``{"Admin", "Teacher", "Student", "",
"root"}`` 上取样（含两个无效值），其余输入均为**合法**值，从而让「角色门控」成为
唯一变量：

* 当 ``current_role != 所需角色`` 时：操作必须返回失败，错误码为
  :attr:`ErrorCode.FORBIDDEN`，且**不产生任何该类型记录**（计数为 0）。对提交操作，
  额外断言存储服务从未被调用（``save_call_count == 0``，角色门控先于一切副作用）。
* 当 ``current_role == 所需角色`` 时：操作被允许进入业务逻辑，凭借合法输入应**成功**
  （``ok is True``、``error_code is None``）并恰好产生一条记录。

为保证 Hypothesis 各用例之间 DB 状态互相隔离，每个用例都构造一套全新的内存
引擎 + 会话 + 仓储（``create_db_engine`` -> ``create_all`` ->
``create_session_factory`` -> ``Repository(session)``）。需要关联实体的操作在调用
被测服务前，先用仓储播种合法的真实实体（教师 / 班级 / 课程 / 作业 / 学生），
使得「角色匹配」时业务逻辑能够顺利完成。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.adapters.storage_service import FakeStorageService
from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import Assignment, Class, Course, Submission, User
from app.repository import Repository
from app.services.assignment_service import (
    AssignmentService,
    CreateAssignmentCommand,
)
from app.services.class_service import ClassService
from app.services.course_service import CourseService
from app.services.submission_service import SubmissionService, UploadedFile
from app.services.user_service import StudentRecord, UserService

# 固定的"当前时间"，使截止时间相关校验具有确定性（与时钟无关）。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 当前角色取样空间：三种合法角色 + 两个无效值（空串、未知角色 "root"）。
# 仅当其等于操作所需角色时，业务逻辑才被允许执行（Property 11）。
_roles = st.sampled_from(["Admin", "Teacher", "Student", "", "root"])


@contextmanager
def _fresh_repo() -> Iterator[Repository]:
    """构造一套全新的内存 SQLite 引擎/会话/Repository（每个 example 间互相隔离）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        yield Repository(session)
    finally:
        session.close()
        engine.dispose()


def _count(repo: Repository, model: type) -> int:
    """统计某 ORM 模型当前的记录条数。"""
    return repo.session.scalar(select(func.count()).select_from(model))


def _count_users_with_role(repo: Repository, role: str) -> int:
    """统计指定角色的用户数（用于断言"未产生该类型记录"）。"""
    return repo.session.scalar(
        select(func.count()).select_from(User).where(User.role == role)
    )


def _seed_teacher(repo: Repository, account: str = "seed-teacher") -> str:
    """播种一名教师用户，返回其主键 id（供班级 teacher_id 外键等使用）。"""
    with repo.transaction():
        teacher = repo.create_user(role="Teacher", account=account)
        return teacher.id


def _seed_class(repo: Repository) -> str:
    """播种 教师 + 班级，返回班级 id。"""
    with repo.transaction():
        teacher = repo.create_user(role="Teacher", account="seed-teacher")
        clazz = repo.create_class(
            school="S", grade="G", major="M", teacher_id=teacher.id
        )
        return clazz.id


def _seed_course(repo: Repository) -> str:
    """播种 教师 + 班级 + 课程，返回课程 id。"""
    with repo.transaction():
        teacher = repo.create_user(role="Teacher", account="seed-teacher")
        clazz = repo.create_class(
            school="S", grade="G", major="M", teacher_id=teacher.id
        )
        course = repo.create_course(
            semester="2024秋", name="数学", class_id=clazz.id
        )
        return course.id


def _seed_assignment_and_student(repo: Repository) -> tuple[str, str]:
    """播种 教师 + 班级 + 课程 + 作业 + 学生，返回 (assignment_id, student_account)。

    作业的允许扩展名为 ``["pdf"]``、最大 5MB、截止时间晚于 ``_NOW``，配合下方提交
    测试的合法文件（``homework.pdf``、非空内容、远小于 5MB）使提交在角色匹配时成功。
    学生的登录账号即其学号（与 ``UserService.create_student`` 的约定一致）。
    """
    with repo.transaction():
        teacher = repo.create_user(role="Teacher", account="seed-teacher")
        clazz = repo.create_class(
            school="S", grade="G", major="M", teacher_id=teacher.id
        )
        course = repo.create_course(
            semester="2024秋", name="数学", class_id=clazz.id
        )
        assignment = repo.create_assignment(
            title="作业一",
            content="说明",
            course_id=course.id,
            allowed_extensions=["pdf"],
            max_file_size_mb=5,
            deadline=_NOW + timedelta(days=1),
        )
        student = repo.create_user(
            role="Student",
            account="stu-001",
            email="alice@example.com",
            student_id="stu-001",
            name="Alice",
            class_id=clazz.id,
        )
        return assignment.id, student.account


# --------------------------------------------------------------------------- #
# 创建教师：要求 Admin（需求 4.2）                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.property
@settings(max_examples=100)
@given(current_role=_roles)
def test_create_teacher_role_gating(current_role: str) -> None:
    """仅 Admin 可创建教师；其余角色一律 FORBIDDEN 且不产生教师记录。"""
    with _fresh_repo() as repo:
        result = UserService(repo).create_teacher(
            current_role, "teacher-account", "teacher@example.com"
        )
        teacher_count = _count_users_with_role(repo, "Teacher")

        if current_role == "Admin":
            assert result.ok is True, f"Admin 创建教师应成功，但得到 {result.error_code}"
            assert result.error_code is None
            assert teacher_count == 1
        else:
            assert result.ok is False
            assert result.error_code == ErrorCode.FORBIDDEN
            assert teacher_count == 0


# --------------------------------------------------------------------------- #
# 创建班级：要求 Teacher（需求 5.1 / 5.2）                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.property
@settings(max_examples=100)
@given(current_role=_roles)
def test_create_class_role_gating(current_role: str) -> None:
    """仅 Teacher 可创建班级；其余角色一律 FORBIDDEN 且不产生班级记录。"""
    with _fresh_repo() as repo:
        teacher_id = _seed_teacher(repo)
        result = ClassService(repo).create_class(
            current_role, "清华大学", "2024级", "软件工程", teacher_id
        )
        class_count = _count(repo, Class)

        if current_role == "Teacher":
            assert result.ok is True, f"Teacher 创建班级应成功，但得到 {result.error_code}"
            assert result.error_code is None
            assert class_count == 1
        else:
            assert result.ok is False
            assert result.error_code == ErrorCode.FORBIDDEN
            assert class_count == 0


# --------------------------------------------------------------------------- #
# 创建学生：要求 Teacher（需求 6.1 / 6.8）                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.property
@settings(max_examples=100)
@given(current_role=_roles)
def test_create_student_role_gating(current_role: str) -> None:
    """仅 Teacher 可创建学生；其余角色一律 FORBIDDEN 且不产生学生记录。"""
    with _fresh_repo() as repo:
        class_id = _seed_class(repo)
        rec = StudentRecord(
            student_id="stu-001", name="Alice", email="alice@example.com"
        )
        result = UserService(repo).create_student(current_role, class_id, rec)
        student_count = _count_users_with_role(repo, "Student")

        if current_role == "Teacher":
            assert result.ok is True, f"Teacher 创建学生应成功，但得到 {result.error_code}"
            assert result.error_code is None
            assert student_count == 1
        else:
            assert result.ok is False
            assert result.error_code == ErrorCode.FORBIDDEN
            assert student_count == 0


# --------------------------------------------------------------------------- #
# 创建课程：要求 Teacher（需求 7.1）                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.property
@settings(max_examples=100)
@given(current_role=_roles)
def test_create_course_role_gating(current_role: str) -> None:
    """仅 Teacher 可创建课程；其余角色一律 FORBIDDEN 且不产生课程记录。"""
    with _fresh_repo() as repo:
        class_id = _seed_class(repo)
        result = CourseService(repo).create_course(
            current_role, "2024秋", "数据结构", class_id
        )
        course_count = _count(repo, Course)

        if current_role == "Teacher":
            assert result.ok is True, f"Teacher 创建课程应成功，但得到 {result.error_code}"
            assert result.error_code is None
            assert course_count == 1
        else:
            assert result.ok is False
            assert result.error_code == ErrorCode.FORBIDDEN
            assert course_count == 0


# --------------------------------------------------------------------------- #
# 创建作业：要求 Teacher（需求 8.1 / 8.2）                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.property
@settings(max_examples=100)
@given(current_role=_roles)
def test_create_assignment_role_gating(current_role: str) -> None:
    """仅 Teacher 可创建作业；其余角色一律 FORBIDDEN 且不产生作业记录。"""
    with _fresh_repo() as repo:
        course_id = _seed_course(repo)
        cmd = CreateAssignmentCommand(
            title="作业一",
            content="说明",
            course_id=course_id,
            allowed_extensions=["pdf"],
            max_file_size_mb=5,
            deadline=_NOW + timedelta(days=1),
        )
        result = AssignmentService(repo).create_assignment(current_role, cmd, _NOW)
        assignment_count = _count(repo, Assignment)

        if current_role == "Teacher":
            assert result.ok is True, f"Teacher 创建作业应成功，但得到 {result.error_code}"
            assert result.error_code is None
            assert assignment_count == 1
        else:
            assert result.ok is False
            assert result.error_code == ErrorCode.FORBIDDEN
            assert assignment_count == 0


# --------------------------------------------------------------------------- #
# 提交作业：要求 Student（需求 9.1 / 9.2）                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.property
@settings(max_examples=100)
@given(current_role=_roles)
def test_submit_role_gating(current_role: str) -> None:
    """仅 Student 可提交作业；其余角色一律 FORBIDDEN，不产生提交记录且零存储调用。"""
    with _fresh_repo() as repo:
        assignment_id, student_account = _seed_assignment_and_student(repo)
        storage = FakeStorageService()
        service = SubmissionService(repo, storage)
        file = UploadedFile(filename="homework.pdf", content=b"hello-bytes")

        result = service.submit(
            current_role, student_account, assignment_id, file, _NOW
        )
        submission_count = _count(repo, Submission)

        if current_role == "Student":
            assert result.ok is True, f"Student 提交作业应成功，但得到 {result.error_code}"
            assert result.error_code is None
            assert submission_count == 1
        else:
            assert result.ok is False
            assert result.error_code == ErrorCode.FORBIDDEN
            assert submission_count == 0
            # 角色门控先于一切副作用：存储服务从未被调用（需求 9.2）。
            assert storage.save_call_count == 0
