# Feature: homework-upload-system, Property 19: 批量计数守恒
"""Property 19：批量计数守恒。

依据 design.md「Correctness Properties」Property 19：

    *For any* 批量创建/导入请求，返回的 ``success_count + failure_count`` 应等于
    请求记录总数，且 ``failure_count`` 等于被跳过的记录数。

**Validates: Requirements 3.3, 6.10**

被测属性（计数守恒）覆盖两条批量路径：

* :meth:`app.services.user_service.UserService.batch_create_users` —— 批量创建用户
  （需求 3.3）。
* :meth:`app.services.user_service.UserService.batch_import_students` —— 教师批量
  导入学生到指定班级（需求 6.10）。

对二者，只要请求记录数落在「可处理区间」``1..MAX_BATCH_SIZE``（即逐条处理、
``error_code is None``），结果都必须满足：

1. ``success_count + failure_count == len(records)`` —— 每条记录要么成功、要么被
   计入失败，二者不重不漏（需求 3.3 / 6.10）。
2. ``failure_count == len(failures)`` —— 失败计数恰为失败明细条数（被跳过的记录数）。

测试策略：

为让计数守恒在「部分成功」场景下得到充分检验，本测试刻意生成 **有效 / 无效 /
重复** 三类混合的记录：

* 有效记录：角色取自 ``{Admin, Teacher, Student}`` / 学号姓名非空白、邮箱形如
  ``local@domain.com``。
* 无效记录：空白必填字段（触发 ``MISSING_REQUIRED_FIELD``）、非法角色
  （``INVALID_ROLE``）、非法邮箱（``INVALID_EMAIL_FORMAT``）。
* 重复记录：``account`` / ``student_id`` 取自较小取值池，使「系统内已存在」与
  「批次内重复」两种重复都易于出现（``DUPLICATE_ACCOUNT`` / ``DUPLICATE_STUDENT_ID``）。

记录列表长度限定在 ``1..30``：远小于 1000 上限以保证落在可处理区间（守恒成立的
前提），同时控制单个 Hypothesis 用例的 DB 写入成本以加速（设计说明：上限 1000
的整体拒绝语义由 Property 20 单独覆盖，本测试不需触及）。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的内存
引擎 + 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``）。``batch_import_students`` 需要一个真实存在的班级作为
``class_id``（``User.class_id`` 为指向 ``classes.id`` 的非空外键），故先创建一名
``Teacher`` 用户再创建一个真实班级。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import (
    CreateUserCommand,
    StudentRecord,
    UserService,
)

# --------------------------------------------------------------------------- #
# 公共构件                                                                      #
# --------------------------------------------------------------------------- #

# 合法邮箱片段：仅小写字母，用于拼出一定合法的邮箱 local@domain.com。
_email_parts = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=6,
)
_valid_emails = st.builds(
    lambda local, domain: f"{local}@{domain}.com", _email_parts, _email_parts
)

# 非法邮箱：空白、缺少 @、缺少域名点号等，触发 INVALID_EMAIL_FORMAT。
_invalid_emails = st.sampled_from(["", "   ", "no-at-sign", "a@b", "@domain.com", "x@"])

# 任意邮箱：有效 / 非法混合。
_any_email = st.one_of(_valid_emails, _invalid_emails)

# 账号 / 学号取值池：刻意取小，使「批次内重复」与「系统内已存在」两种重复易出现；
# 同时混入空白以触发 MISSING_REQUIRED_FIELD。均不含空格（与含空格的教师账号隔离）。
_id_pool = st.sampled_from(["a", "b", "c", "dup", "x1", "x2", "", "   "])

# 教师账号：固定常量且含空格；学生账号取 account == student_id，而学号取自不含
# 空格的取值池，故教师账号永不与任一学生账号相撞（隔离与本属性无关的账号唯一约束）。
_TEACHER_ACCOUNT = "teacher fixture account"


# --------------------------------------------------------------------------- #
# 生成器：批量创建用户的混合记录（有效 / 无效 / 重复）                          #
# --------------------------------------------------------------------------- #
@st.composite
def _user_records(draw: st.DrawFn) -> CreateUserCommand:
    """生成一条 UserRecord（== CreateUserCommand），有效/无效/重复混合。"""
    role = draw(
        st.one_of(
            st.sampled_from(["Admin", "Teacher", "Student"]),  # 合法
            st.sampled_from(["", "  ", "Root", "guest"]),  # 缺失 / 非法
        )
    )
    account = draw(_id_pool)
    email = draw(_any_email)
    password = draw(st.one_of(st.none(), st.text(max_size=6)))
    return CreateUserCommand(
        role=role, account=account, email=email, password=password
    )


# --------------------------------------------------------------------------- #
# 生成器：批量导入学生的混合记录（有效 / 无效 / 重复）                          #
# --------------------------------------------------------------------------- #
@st.composite
def _student_records(draw: st.DrawFn) -> StudentRecord:
    """生成一条 StudentRecord，有效/无效/重复混合。"""
    student_id = draw(_id_pool)
    name = draw(
        st.one_of(
            st.text(
                alphabet=st.characters(min_codepoint=33, max_codepoint=126),
                min_size=1,
                max_size=8,
            ),  # 非空白姓名
            st.sampled_from(["", "   "]),  # 缺失
        )
    )
    email = draw(_any_email)
    password = draw(st.one_of(st.none(), st.text(max_size=6)))
    return StudentRecord(
        student_id=student_id, name=name, email=email, password=password
    )


@pytest.mark.property
@settings(max_examples=100)
@given(records=st.lists(_user_records(), min_size=1, max_size=30))
def test_batch_create_users_count_is_conserved(
    records: list[CreateUserCommand],
) -> None:
    """batch_create_users：success + failure == 记录数，且 failure == len(failures)。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)
        result = UserService(repo).batch_create_users(records)

        # 记录数落在 1..MAX_BATCH_SIZE，应为逐条处理结果（非整体拒绝）。
        assert result.error_code is None, (
            f"1..30 条记录应逐条处理，却整体拒绝：{result.error_code}"
        )

        # 计数守恒（需求 3.3）：成功 + 失败 == 请求记录总数。
        assert result.success_count + result.failure_count == len(records)
        # 失败计数恰为失败明细条数（被跳过的记录数）。
        assert result.failure_count == len(result.failures)
        # 计数非负（防御性）。
        assert result.success_count >= 0
        assert result.failure_count >= 0
    finally:
        session.close()
        engine.dispose()


@pytest.mark.property
@settings(max_examples=100)
@given(records=st.lists(_student_records(), min_size=1, max_size=30))
def test_batch_import_students_count_is_conserved(
    records: list[StudentRecord],
) -> None:
    """batch_import_students：success + failure == 记录数，且 failure == len(failures)。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # User.class_id 指向真实班级；Class.teacher_id 为非空外键。
        # 先建一名 Teacher（账号含空格，永不与学生学号/账号相撞），再建一个真实班级。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=_TEACHER_ACCOUNT)
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            class_id = clazz.id

        result = UserService(repo).batch_import_students(
            current_role="Teacher", class_id=class_id, records=records
        )

        # 记录数落在 1..MAX_BATCH_SIZE，且角色为 Teacher，应为逐条处理结果。
        assert result.error_code is None, (
            f"1..30 条记录应逐条处理，却整体拒绝：{result.error_code}"
        )

        # 计数守恒（需求 6.10）：成功 + 失败 == 请求记录总数。
        assert result.success_count + result.failure_count == len(records)
        # 失败计数恰为失败明细条数（被跳过的记录数）。
        assert result.failure_count == len(result.failures)
        # 计数非负（防御性）。
        assert result.success_count >= 0
        assert result.failure_count >= 0
    finally:
        session.close()
        engine.dispose()
