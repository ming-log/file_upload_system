# Feature: homework-upload-system, Property 8: 必填字段缺失统一拒绝
"""Property 8：必填字段缺失统一拒绝。

依据 design.md「Correctness Properties」Property 8：

    *For any* 创建命令，若其任一必填字段为空或仅含空白字符，则创建被拒绝、
    不产生任何记录，并返回“必填字段缺失错误”。（适用于登录账号/密码、用户
    role/account、教师 account/email、班级 school/grade/major、课程
    semester/name/class、作业 title/course/deadline。）

**Validates: Requirements 1.6, 2.6, 4.4, 5.7, 6.9, 7.6, 8.5**

测试策略：

本属性横跨多个服务的「创建/登录」入口，统一断言「任一必填字段空白 ->
:attr:`ErrorCode.MISSING_REQUIRED_FIELD` 且零记录」。为清晰起见，每个操作各用
一个独立的 ``@given`` 函数验证：

* **登录**（需求 1.6）：``AuthService.login`` 的 ``account`` / ``password``。
* **创建用户**（需求 2.6）：``UserService.create_user`` 的 ``role`` / ``account``
  （``email`` 不在 create_user 的必填范围内，见 user_service 模块文档）。
* **创建教师**（需求 4.4）：``UserService.create_teacher`` 的 ``account`` /
  ``email``（以 ``Admin`` 通过角色门控）。
* **创建学生**（需求 6.9）：``UserService.create_student`` 的 ``student_id`` /
  ``name`` / ``email``（以 ``Teacher`` 通过角色门控）。
* **创建班级**（需求 5.7）：``ClassService.create_class`` 的 ``school`` /
  ``grade`` / ``major``（以 ``Teacher`` 通过角色门控）。
* **创建课程**（需求 7.6）：``CourseService.create_course`` 的 ``semester`` /
  ``name`` / ``class_id``（以 ``Teacher`` 通过角色门控；``class_id`` 空白触发
  「必填缺失」而非「班级不存在」，因必填校验先于存在性校验）。
* **创建作业**（需求 8.5）：``AssignmentService.create_assignment`` 的 ``title``
  / ``course_id`` / ``deadline``（以 ``Teacher`` 通过角色门控；``deadline`` 的
  「缺失」以 ``None`` 表达）。

公共做法：

* 每个操作以「正确所需角色」入参，使角色门控通过，从而让「必填字段缺失」成为
  真正触发拒绝的检查（而非 ``FORBIDDEN``）。
* 输入生成保证 **至少一个** 必填字段为空白（``""`` / 空格 / 制表符 / 换行 等，
  对作业 ``deadline`` 则为 ``None``），其余必填字段取合法的非空白值。
* 每个 Hypothesis 用例内部构造一套全新的内存 SQLite 引擎 + 会话 + 仓储，保证
  用例间状态隔离；操作后断言对应实体表零记录（不产生任何记录）。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import Assignment, Class, Course, User
from app.repository import Repository
from app.services.assignment_service import (
    AssignmentService,
    CreateAssignmentCommand,
)
from app.services.auth_service import AuthService
from app.services.class_service import ClassService
from app.services.course_service import CourseService
from app.services.user_service import (
    CreateUserCommand,
    StudentRecord,
    UserService,
)

# 固定“当前时间”，使作业截止时间相关输入具有确定性。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 空白/缺失取值：空串、纯空格、制表符、换行等——validate_required 一律判为“缺失”。
_BLANKS = st.sampled_from(["", " ", "  ", "\t", "\n", " \t ", "\r\n"])

# 合法非空白文本：可见 ASCII（码点 33..126，不含空白），长度 1..20。
# 保证 validate_required 通过，并落在各字段长度上限（如 1..20）内。
_VALID_TEXT = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 邮箱片段：仅小写字母，用于拼出一定合法的邮箱 local@domain.com。
_EMAIL_PARTS = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=8,
)


@st.composite
def _valid_emails(draw: st.DrawFn) -> str:
    """构造一定满足邮箱格式（恰好一个 @、本地名非空、域名非空且含点号）的邮箱。"""
    local = draw(_EMAIL_PARTS)
    domain = draw(_EMAIL_PARTS)
    return f"{local}@{domain}.com"


@st.composite
def _with_at_least_one_blank(
    draw: st.DrawFn, valid_strategies: tuple[st.SearchStrategy, ...]
) -> tuple:
    """为给定的若干必填字段生成取值，且保证 **至少一个** 字段为空白。

    Args:
        valid_strategies: 各字段“合法（非空白）取值”的策略元组，顺序与字段一致。

    Returns:
        与 ``valid_strategies`` 等长的取值元组：被选中的字段取空白值，其余取合法值。
    """
    n = len(valid_strategies)
    flags = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    if not any(flags):
        # 确保至少一个必填字段为空白（命中被测属性的输入空间）。
        flags[draw(st.integers(min_value=0, max_value=n - 1))] = True
    values = []
    for is_blank, valid_strategy in zip(flags, valid_strategies):
        values.append(draw(_BLANKS) if is_blank else draw(valid_strategy))
    return tuple(values)


def _fresh_repo() -> Iterator[Repository]:
    """构造一套全新的内存 SQLite 引擎/会话/仓储（每个 example 隔离）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session = create_session_factory(engine)()
    repo = Repository(session)
    try:
        yield repo
    finally:
        session.close()
        engine.dispose()


def _count(repo: Repository, model: type) -> int:
    """统计某实体表当前记录数（用于断言“不产生任何记录”）。"""
    return repo.session.scalar(select(func.count()).select_from(model))


# --------------------------------------------------------------------------- #
# 登录（需求 1.6）：account / password 任一空白 -> MISSING_REQUIRED_FIELD       #
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=100)
@given(fields=_with_at_least_one_blank((_VALID_TEXT, _VALID_TEXT)))
def test_login_missing_required_field_rejected(fields: tuple[str, str]) -> None:
    """登录 account/password 任一空白 -> 拒绝、不签发令牌、MISSING_REQUIRED_FIELD（需求 1.6）。"""
    account, password = fields
    gen = _fresh_repo()
    repo = next(gen)
    try:
        result = AuthService(repo).login(account, password, _NOW)

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        # 不签发令牌（登录无记录概念，以“无令牌”表达“不产生任何结果”）。
        assert result.token is None
        assert result.role is None
    finally:
        gen.close()


# --------------------------------------------------------------------------- #
# 创建用户（需求 2.6）：role / account 任一空白 -> MISSING_REQUIRED_FIELD       #
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=100)
@given(
    fields=_with_at_least_one_blank((_VALID_TEXT, _VALID_TEXT)),
    email=_valid_emails(),
)
def test_create_user_missing_required_field_rejected(
    fields: tuple[str, str], email: str
) -> None:
    """create_user 的 role/account 任一空白 -> 拒绝、零用户、MISSING_REQUIRED_FIELD（需求 2.6）。"""
    role, account = fields
    gen = _fresh_repo()
    repo = next(gen)
    try:
        # email 取合法值：create_user 的必填范围仅 role/account，且必填校验先行。
        cmd = CreateUserCommand(role=role, account=account, email=email)
        result = UserService(repo).create_user(cmd)

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert result.user_id is None
        # 不产生任何用户记录。
        assert _count(repo, User) == 0
    finally:
        gen.close()


# --------------------------------------------------------------------------- #
# 创建教师（需求 4.4）：account / email 任一空白 -> MISSING_REQUIRED_FIELD      #
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=100)
@given(fields=_with_at_least_one_blank((_VALID_TEXT, _valid_emails())))
def test_create_teacher_missing_required_field_rejected(
    fields: tuple[str, str],
) -> None:
    """Admin 创建教师 account/email 任一空白 -> 拒绝、零用户、MISSING_REQUIRED_FIELD（需求 4.4）。"""
    account, email = fields
    gen = _fresh_repo()
    repo = next(gen)
    try:
        # current_role="Admin" 通过角色门控，使必填检查成为触发拒绝的检查。
        result = UserService(repo).create_teacher("Admin", account, email)

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert result.account is None
        # 不产生任何用户记录。
        assert _count(repo, User) == 0
    finally:
        gen.close()


# --------------------------------------------------------------------------- #
# 创建学生（需求 6.9）：student_id / name / email 任一空白 -> MISSING           #
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=100)
@given(
    fields=_with_at_least_one_blank((_VALID_TEXT, _VALID_TEXT, _valid_emails())),
    class_id=_VALID_TEXT,
)
def test_create_student_missing_required_field_rejected(
    fields: tuple[str, str, str], class_id: str
) -> None:
    """Teacher 创建学生 student_id/name/email 任一空白 -> 拒绝、零用户、MISSING（需求 6.9）。"""
    student_id, name, email = fields
    gen = _fresh_repo()
    repo = next(gen)
    try:
        # current_role="Teacher" 通过角色门控；必填校验先于学号唯一性/班级关联。
        rec = StudentRecord(student_id=student_id, name=name, email=email)
        result = UserService(repo).create_student("Teacher", class_id, rec)

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert result.user_id is None
        # 不产生任何用户记录。
        assert _count(repo, User) == 0
    finally:
        gen.close()


# --------------------------------------------------------------------------- #
# 创建班级（需求 5.7）：school / grade / major 任一空白 -> MISSING              #
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=100)
@given(fields=_with_at_least_one_blank((_VALID_TEXT, _VALID_TEXT, _VALID_TEXT)))
def test_create_class_missing_required_field_rejected(
    fields: tuple[str, str, str],
) -> None:
    """Teacher 创建班级 school/grade/major 任一空白 -> 拒绝、零班级、MISSING（需求 5.7）。"""
    school, grade, major = fields
    gen = _fresh_repo()
    repo = next(gen)
    try:
        # current_role="Teacher" 通过角色门控；必填校验先于长度校验与创建。
        result = ClassService(repo).create_class(
            "Teacher", school, grade, major, teacher_id="t-1"
        )

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert result.class_id is None
        # 不产生任何班级记录。
        assert _count(repo, Class) == 0
    finally:
        gen.close()


# --------------------------------------------------------------------------- #
# 创建课程（需求 7.6）：semester / name / class_id 任一空白 -> MISSING          #
# --------------------------------------------------------------------------- #


@pytest.mark.property
@settings(max_examples=100)
@given(fields=_with_at_least_one_blank((_VALID_TEXT, _VALID_TEXT, _VALID_TEXT)))
def test_create_course_missing_required_field_rejected(
    fields: tuple[str, str, str],
) -> None:
    """Teacher 创建课程 semester/name/class_id 任一空白 -> 拒绝、零课程、MISSING（需求 7.6）。"""
    semester, name, class_id = fields
    gen = _fresh_repo()
    repo = next(gen)
    try:
        # current_role="Teacher" 通过角色门控；必填校验先于班级存在性校验，
        # 故空白 class_id 触发 MISSING_REQUIRED_FIELD 而非 CLASS_NOT_FOUND。
        result = CourseService(repo).create_course("Teacher", semester, name, class_id)

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert result.course_id is None
        # 不产生任何课程记录。
        assert _count(repo, Course) == 0
    finally:
        gen.close()


# --------------------------------------------------------------------------- #
# 创建作业（需求 8.5）：title / course_id / deadline 任一空 -> MISSING          #
# --------------------------------------------------------------------------- #


@st.composite
def _assignment_missing_inputs(
    draw: st.DrawFn,
) -> tuple[str, str, datetime | None]:
    """生成 (title, course_id, deadline)，保证 title/course_id/deadline 至少一个“缺失”。

    title / course_id 的“缺失”以空白字符串表达，deadline 的“缺失”以 ``None`` 表达。
    """
    flags = draw(st.lists(st.booleans(), min_size=3, max_size=3))
    if not any(flags):
        flags[draw(st.integers(min_value=0, max_value=2))] = True
    title = draw(_BLANKS) if flags[0] else draw(_VALID_TEXT)
    course_id = draw(_BLANKS) if flags[1] else draw(_VALID_TEXT)
    # deadline 合法值须晚于 now（避免触碰截止时间无效分支，尽管必填校验先行）。
    deadline = None if flags[2] else _NOW + timedelta(days=1)
    return title, course_id, deadline


@pytest.mark.property
@settings(max_examples=100)
@given(inputs=_assignment_missing_inputs())
def test_create_assignment_missing_required_field_rejected(
    inputs: tuple[str, str, datetime | None],
) -> None:
    """Teacher 创建作业 title/course_id/deadline 任一缺失 -> 拒绝、零作业、MISSING（需求 8.5）。"""
    title, course_id, deadline = inputs
    gen = _fresh_repo()
    repo = next(gen)
    try:
        # 其余字段取合法值，使必填校验成为触发拒绝的检查；必填校验先于
        # 长度/扩展名/大小/课程存在性/截止时间校验。
        cmd = CreateAssignmentCommand(
            title=title,
            content="",
            course_id=course_id,
            allowed_extensions=("pdf",),
            max_file_size_mb=5,
            deadline=deadline,
        )
        result = AssignmentService(repo).create_assignment("Teacher", cmd, _NOW)

        assert result.ok is False
        assert result.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert result.assignment_id is None
        # 不产生任何作业记录。
        assert _count(repo, Assignment) == 0
    finally:
        gen.close()
