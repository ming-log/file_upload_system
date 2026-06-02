# Feature: homework-upload-system, Property 31: 存储失败零重试零记录
"""Property 31：存储失败零重试零记录（design.md「Correctness Properties」）。

*For any* 通过了存储前全部校验（角色、作业存在性、空文件、扩展名、大小、截止时间）
的提交，当 :class:`StorageService` 返回存储错误或超时时，:class:`SubmissionService`
对存储 :meth:`StorageService.save` **恰好调用一次（0 次重试）**、**不创建任何提交
记录**，并返回「文件保存失败」对应的存储错误码（失败 -> ``STORAGE_FAILED``、
超时 -> ``STORAGE_TIMEOUT``）。

**Validates: Requirements 10.3**

被测对象：:meth:`app.services.submission_service.SubmissionService.submit`。

可测试性 / 注入策略：
* 每个用例使用全新的内存 SQLite 引擎 + :class:`Repository`，保证用例间状态隔离。
* 构造完整关联链（Teacher、Class、Course、Assignment、Student）并提交：
    - ``Assignment`` 允许扩展名为 ``["pdf"]``、``max_file_size_mb=5``、截止时间为
      ``now + 1 天``（未来），确保存储前各项校验均**通过**，从而进入存储分支。
* 存储以 :class:`FakeStorageService` 注入，按生成的 ``failure_mode`` 模拟失败/超时：
    - ``mode == "fail"``   -> ``FakeStorageService(fail=True)``   -> ``STORAGE_FAILED``；
    - ``mode == "timeout"`` -> ``FakeStorageService(timeout=True)`` -> ``STORAGE_TIMEOUT``。
  其 :attr:`FakeStorageService.save_call_count` 用于断言「恰好一次、0 重试」。
* 未注入 :class:`EmailService`：存储在创建记录前即失败，邮件路径本就不会触达。

输入生成说明：
* ``base`` 取自小写字母（码点 97..122），长度 1..20，拼接 ``".pdf"`` 后经
  :func:`os.path.splitext` 必得扩展名 ``".pdf"``，满足作业允许集合（不区分大小写）。
* ``content`` 为长度 1..1024 的非空字节内容，远小于 5MB 上限，确保空文件与
  大小校验均通过。
"""

from __future__ import annotations

from datetime import datetime, timedelta

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

# 固定的「当前时间」；截止时间取其后一天，保证提交未超过截止时间（需求 9.6 通过）。
_FIXED_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 学生账号：提交入参，submit 通过该账号解析出学生主键与邮箱。
_STUDENT_ACCOUNT = "student-acct"

# 文件名主干：小写字母、长度 1..20，拼接 ".pdf" 后扩展名稳定为 pdf（满足允许集合）。
_filename_base = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=20,
)

# 非空文件内容：长度 1..1024 字节，远小于 5MB，确保非空且不超限。
_file_content = st.binary(min_size=1, max_size=1024)


@pytest.mark.property
@settings(max_examples=100)
@given(
    base=_filename_base,
    content=_file_content,
    failure_mode=st.sampled_from(["fail", "timeout"]),
)
def test_storage_failure_no_retry_no_record(
    base: str, content: bytes, failure_mode: str
) -> None:
    """存储失败/超时：save 恰好调用一次、不创建提交记录、返回对应存储错误码。"""
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 构造完整关联链，使存储前各项校验通过（角色、作业、空文件、扩展名、大小、截止时间）。
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
                deadline=_FIXED_NOW + timedelta(days=1),
            )
            repo.create_user(
                role="Student",
                account=_STUDENT_ACCOUNT,
                student_id="stu-1",
                class_id=clazz.id,
            )
            assignment_id = assignment.id

        # 存储按模式模拟失败/超时。
        storage = FakeStorageService(
            fail=(failure_mode == "fail"),
            timeout=(failure_mode == "timeout"),
        )

        file = UploadedFile(filename=base + ".pdf", content=content)
        service = SubmissionService(repo, storage)

        result = service.submit(
            "Student", _STUDENT_ACCOUNT, assignment_id, file, _FIXED_NOW
        )

        # (a) 提交失败。
        assert result.ok is False
        assert result.submission_id is None

        # (b) 错误码与存储结果一致（失败 -> STORAGE_FAILED；超时 -> STORAGE_TIMEOUT）。
        expected_code = (
            ErrorCode.STORAGE_FAILED
            if failure_mode == "fail"
            else ErrorCode.STORAGE_TIMEOUT
        )
        assert result.error_code == expected_code

        # (c) 存储 save 恰好被调用一次（0 次重试，需求 10.3）。
        assert storage.save_call_count == 1, (
            f"存储应恰好调用一次（0 重试），实际 {storage.save_call_count} 次"
        )

        # (d) 未创建任何提交记录。
        submission_count = session.scalar(select(func.count()).select_from(Submission))
        assert submission_count == 0, "存储失败时不应创建任何提交记录"
    finally:
        session.close()
        engine.dispose()
