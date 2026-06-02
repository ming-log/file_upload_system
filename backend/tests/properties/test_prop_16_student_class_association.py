# Feature: homework-upload-system, Property 16: 学生成功创建关联至当前班级
"""Property 16：学生成功创建关联至当前班级。

依据 design.md「Correctness Properties」Property 16：

    *For any* 在指定班级内成功创建的学生，其 ``class_id`` 应等于该指定班级；
    批量导入中所有有效记录同样关联至该班级。

**Validates: Requirements 6.4, 6.5**

测试策略：
对任意「学号 / 姓名 均非空白、邮箱符合『本地名@域名』格式」的合法学生记录，并以一个
**已存在** 的班级标识作为 ``class_id``，由一名 ``Teacher`` 调用
:meth:`app.services.user_service.UserService.create_student` 应成功
（``result.ok is True``）。随后通过 ``repo.get_user_by_account(student_id)``
（学生的 ``account`` 即其 ``student_id``）取回持久化后的用户，断言其
``class_id`` 等于所传入的班级标识（需求 6.4「关联到当前班级」）。

为保证每个 Hypothesis 用例之间 DB 状态相互隔离，测试体内部构造一个全新的内存引擎
+ 仓储（``create_db_engine`` -> ``create_all`` -> ``create_session_factory``
-> ``Repository(session)``）。

班级存在性说明：``create_student`` 不校验班级是否存在，但 ``User.class_id`` 是
指向 ``classes.id`` 的非空外键。若传入不存在的 ``class_id``，写入会触发
``IntegrityError``。故先创建一名 ``Teacher`` 用户，再创建一个真实班级
（``repo.create_class(...)``）并提交，使用其 ``id`` 作为 ``class_id``。

输入生成说明：``validate_required`` 将纯空白视为「缺失」。为确保归一化后仍满足
「非空白」与「合法邮箱」约束，本测试从可见 ASCII（码点 33..126，不含空白）构造
学号 / 姓名 / 邮箱的本地名与域名部分；邮箱固定形如 ``<local>@<domain>.com``，
保证恰好一个 ``@``、本地名与域名非空且域名含点号（满足 :func:`validate_email`）。
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.user_service import StudentRecord, UserService

# 非空白字符串：从可见 ASCII（码点 33..126，不含空白）取字符，保证
# validate_required 通过（覆盖学号 / 姓名 的合法输入空间）。
_non_blank = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 邮箱片段：不含 '@' 与 '.' 的可见 ASCII 字符串，作为本地名 / 域名标签。
_email_part = st.text(
    alphabet=st.characters(
        min_codepoint=33,
        max_codepoint=126,
        blacklist_characters="@.",
    ),
    min_size=1,
    max_size=15,
)

# 合法邮箱：<local>@<domain>.com —— 恰好一个 '@'、本地名/域名非空且域名含点号。
_valid_emails = st.builds(
    lambda local, domain: f"{local}@{domain}.com",
    _email_part,
    _email_part,
)

# 教师账号：使用固定且足够长（>20 字符）的常量，保证与生成的学号
# （student_id，最长 20 字符且即学生 account）绝不重合，避免 users.account
# 的唯一约束冲突——该约束与 Property 16（关联校验）无关，属测试夹具范畴。
_TEACHER_ACCOUNT = "teacher-fixture-account-0123456789"


@pytest.mark.property
@settings(max_examples=100)
@given(
    student_id=_non_blank,
    name=_non_blank,
    email=_valid_emails,
    password=st.one_of(st.none(), _non_blank),
)
def test_student_creation_associates_to_current_class(
    student_id: str,
    name: str,
    email: str,
    password: str | None,
) -> None:
    """合法学生记录 + 已存在班级 -> 创建成功且持久化用户的 class_id 等于该班级。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # User.class_id 为指向 classes.id 的非空外键；Class.teacher_id 亦为非空外键。
        # 先建一名 Teacher，再建一个真实班级作为「当前班级」。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=_TEACHER_ACCOUNT)
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            class_id = clazz.id

        rec = StudentRecord(
            student_id=student_id,
            name=name,
            email=email,
            password=password,
        )
        result = UserService(repo).create_student("Teacher", class_id, rec)

        # 需求 6.4：在班级内创建学生成功。
        assert result.ok is True, f"学生创建失败：error_code={result.error_code}"
        assert result.error_code is None
        assert result.student_id == student_id

        # 需求 6.4：持久化的学生确实存在，且关联到当前班级（account == student_id）。
        user = repo.get_user_by_account(student_id)
        assert user is not None
        assert user.class_id == class_id
    finally:
        session.close()
        engine.dispose()
