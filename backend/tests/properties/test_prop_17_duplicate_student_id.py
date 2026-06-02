# Feature: homework-upload-system, Property 17: 学号重复被跳过或拒绝
"""Property 17：学号重复被跳过或拒绝。

依据 design.md「Correctness Properties」Property 17：

    *For any* 学号在系统内已存在或在本批次内重复出现的记录，单条创建应返回
    "学号重复错误"且零创建；批量导入应跳过该记录、继续处理其余记录，并在失败明细
    中包含该学号与失败原因。

**Validates: Requirements 6.6, 6.7**

测试范围说明：

本测试聚焦 Property 17 的「单条创建」路径（需求 6.7）——这是当前已实现的能力：
:meth:`app.services.user_service.UserService.create_student`。批量导入跳过重复
（需求 6.6）由任务 7.9 的 ``batch_import_students`` 负责，将在其属性测试
（Property 18/19/20）中覆盖；本文件不依赖该方法的存在。

被测属性（单条创建）：
对任意已存在学号 ``S``（先以 ``S`` 成功创建一名学生），再以**相同学号** ``S``
（姓名/邮箱不同）创建第二名学生时，应满足：

* ``result.ok is False``；
* ``result.error_code == ErrorCode.DUPLICATE_STUDENT_ID``（需求 6.7）；
* 系统内 ``student_id == S`` 的用户恰好仅有一条记录（零新增）。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的
内存引擎 + 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``）。``User.class_id`` 关联到一个**真实存在**的班级，
而 ``Class.teacher_id`` 为非空外键，故先创建一名 ``Teacher`` 用户，再创建一个班级
作为学生归属班级。

输入生成说明：``validate_required`` 将纯空白视为「缺失」，邮箱须符合「本地名@域名」
格式。为隔离「学号重复」这一被测属性、避免被其它校验（必填/邮箱格式）干扰，
学号/姓名均取自可见非空白 ASCII（码点 33..126），邮箱由小写字母拼成
``local@domain.com``。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import User
from app.repository import Repository
from app.services.user_service import StudentRecord, UserService

# 学号 / 姓名：非空白、长度 1..20 的可见 ASCII（码点 33..126），保证 validate_required
# 通过，且落在 User.student_id / User.name 的存储宽度内。
_non_blank_1_20 = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 邮箱片段：仅小写字母，用于拼出一定合法的邮箱 local@domain.com。
_email_parts = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=8,
)

# 教师账号：固定常量，且**含空格**。学生账号取 ``account = student_id``，而学号由
# 可见非空白 ASCII（码点 33..126，不含空格）生成；故含空格的教师账号永远不会与任何
# 学生账号相撞。这样可隔离「学号重复」这一被测属性，避免「教师账号 == 学生学号」
# 导致 account 唯一约束误触发（与 Property 17 无关的前置条件污染）。
_TEACHER_ACCOUNT = "teacher account"


@st.composite
def _valid_emails(draw: st.DrawFn) -> str:
    """构造一定满足邮箱格式（恰好一个 @、本地名非空、域名非空且含点号）的邮箱。"""
    local = draw(_email_parts)
    domain = draw(_email_parts)
    return f"{local}@{domain}.com"


@pytest.mark.property
@settings(max_examples=100)
@given(
    student_id=_non_blank_1_20,
    name1=_non_blank_1_20,
    email1=_valid_emails(),
    name2=_non_blank_1_20,
    email2=_valid_emails(),
)
def test_duplicate_student_id_is_rejected_with_zero_new_records(
    student_id: str,
    name1: str,
    email1: str,
    name2: str,
    email2: str,
) -> None:
    """以同一学号二次创建学生必被拒绝（DUPLICATE_STUDENT_ID）且零新增记录。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # User.class_id 指向真实班级；Class.teacher_id 为非空外键。
        # 先建一名 Teacher（账号含空格，永不与学生学号/账号相撞），再建一个班级。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=_TEACHER_ACCOUNT)
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            class_id = clazz.id

        service = UserService(repo)

        # 第一次创建：学号 S，应成功（其余字段均合法，仅测试学号唯一性）。
        first = service.create_student(
            "Teacher",
            class_id,
            StudentRecord(student_id=student_id, name=name1, email=email1),
        )
        assert first.ok is True, f"首次创建学生应成功，但得到 {first.error_code}"
        assert first.error_code is None
        assert first.student_id == student_id

        # 第二次创建：相同学号 S（姓名/邮箱不同），应被拒绝（需求 6.7）。
        second = service.create_student(
            "Teacher",
            class_id,
            StudentRecord(student_id=student_id, name=name2, email=email2),
        )
        assert second.ok is False, "相同学号的二次创建必须被拒绝"
        assert second.error_code == ErrorCode.DUPLICATE_STUDENT_ID
        assert second.user_id is None

        # 系统内该学号恰好仅有一条记录（重复学号不应产生新增记录）。
        students = list(
            repo.session.scalars(
                select(User).where(User.student_id == student_id)
            ).all()
        )
        assert len(students) == 1, "重复学号不应产生新增记录"

        # 该记录即首次创建的学生（原记录未被覆盖/篡改）。
        stored = students[0]
        assert stored.id == first.user_id
        assert stored.student_id == student_id
        assert stored.name == name1
        assert stored.email == email1
        assert stored.class_id == class_id
    finally:
        session.close()
        engine.dispose()
