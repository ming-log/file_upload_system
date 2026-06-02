# Feature: homework-upload-system, Property 29: 空文件拒绝
"""Property 29：空文件拒绝（design.md「Correctness Properties」Property 29）。

    *For any* 缺失文件或文件大小为 0 字节的提交请求，提交应被拒绝、不创建作业
    提交记录，并返回“文件为空错误”。

**Validates: Requirements 9.3**

被测对象：:meth:`app.services.submission_service.SubmissionService.submit`。

提交流程的校验顺序为：角色门控 -> 作业存在性 -> 空文件 -> 扩展名 -> 大小 ->
截止时间 -> 存储 -> 创建记录。因此为了让流程恰好抵达“空文件”这一被测分支，本
测试构造一个合法的 Student 角色与一个已存在的有效作业（``allowed=["pdf"]``、
``max=5MB``、截止时间晚于固定 ``now``），随后提交一个“缺失（None）”或“0 字节”
的文件，断言：

* 结果失败且错误码为 :attr:`ErrorCode.EMPTY_FILE`；
* 存储服务从未被调用（``FakeStorageService.save_call_count == 0``）——空文件在
  存储之前即被拒绝；
* 不产生任何提交记录（``Submission`` 行数为 0）。

输入生成（``st.one_of`` 覆盖两条空文件路径）：

* ``None``：模拟“缺失文件”；
* ``UploadedFile(filename=<任意 .pdf 名>, content=b"")``：模拟“0 字节文件”。
  文件名可为任意值——空文件检查先于扩展名检查，故无论扩展名如何都应触发
  ``EMPTY_FILE``。

为保证 Hypothesis 各用例之间 DB 状态互相隔离，测试体内部每次都构造一套全新的
内存引擎 + 会话 + 仓储，并写入完整的关联链（Teacher/Class/Course/Assignment/
Student）。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.adapters.storage_service import FakeStorageService
from app.core.errors import ErrorCode
from app.db import create_all, create_db_engine, create_session_factory
from app.models import Submission
from app.repository import Repository
from app.services.submission_service import SubmissionService, UploadedFile

# 固定的“当前时间”，使截止时间相关判定具有确定性（与真实时钟无关）。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 非空白文件名（任意 .pdf 名）：空文件检查先于扩展名检查，扩展名不影响结果。
_pdf_filenames = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
).map(lambda stem: f"{stem}.pdf")

# 空文件的两种形态：缺失文件（None）或 0 字节文件。
_empty_files = st.one_of(
    st.none(),
    _pdf_filenames.map(lambda name: UploadedFile(filename=name, content=b"")),
)


@pytest.mark.property
@settings(max_examples=100)
@given(file=_empty_files)
def test_empty_file_submission_rejected(file: Optional[UploadedFile]) -> None:
    """缺失或 0 字节文件提交应被拒绝（EMPTY_FILE），存储未被调用且不创建提交记录。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 构造完整关联链：Teacher -> Class -> Course -> Assignment -> Student。
        # 作业：allowed=["pdf"]、max=5MB、截止时间晚于 now（未过期），使流程能抵达
        # “空文件”校验分支（角色 -> 作业存在性 -> 空文件）。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account="teacher-acct")
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            course = repo.create_course(
                semester="2024-Spring", name="Course", class_id=clazz.id
            )
            assignment = repo.create_assignment(
                title="HW",
                course_id=course.id,
                allowed_extensions=["pdf"],
                max_file_size_mb=5,
                deadline=_NOW + timedelta(days=1),
            )
            student = repo.create_user(
                role="Student",
                account="student-acct",
                student_id="stu-1",
                class_id=clazz.id,
            )
            assignment_id = assignment.id
            student_account = student.account

        storage = FakeStorageService()
        service = SubmissionService(repo, storage)

        # 以 Student 角色提交一个缺失/空文件（需求 9.3）。
        result = service.submit(
            "Student", student_account, assignment_id, file, _NOW
        )

        # 提交被拒绝并返回“文件为空错误”。
        assert result.ok is False
        assert result.error_code == ErrorCode.EMPTY_FILE
        assert result.submission_id is None

        # 空文件在存储之前即被拒绝：存储从未被调用。
        assert storage.save_call_count == 0

        # 不产生任何提交记录。
        submission_count = repo.session.scalar(
            select(func.count()).select_from(Submission)
        )
        assert submission_count == 0
    finally:
        session.close()
        engine.dispose()
