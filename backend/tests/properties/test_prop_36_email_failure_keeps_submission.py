# Feature: homework-upload-system, Property 36: 邮件最终失败不影响提交记录
"""Property 36：邮件最终失败不影响提交记录（design.md「Correctness Properties」）。

*For any* 邮箱非空但累计 3 次发送尝试均失败的提交，系统应记录一条包含提交记录标识
与失败原因的发送失败日志，且对应作业提交记录仍保持存在且有效（不回滚）。

**Validates: Requirements 11.6**

被测对象：:meth:`app.adapters.email_service.EmailService.notify_submission`
（异步）。该方法在邮箱非空时立即发起发送；单次失败后按
:func:`next_attempt_schedule` 以默认间隔最多重试 :data:`DEFAULT_MAX_RETRIES`（2）
次（累计 3 次尝试）；全部失败时记录一条 ERROR 级别、含 ``submission_id`` 与失败
原因的日志，并**正常返回**（绝不抛出），从而保持已创建的提交记录有效、不回滚。

可测试性 / 注入策略（构造函数注入全部副作用依赖，无需真实 SMTP / 真实等待）：

* ``sender``：始终失败的异步 fake，并统计调用次数。通过生成的 ``failure_mode``
  覆盖两条失败路径——抛普通异常（``except Exception``）与抛
  :class:`asyncio.TimeoutError`（``except asyncio.TimeoutError``，对应需求 11.4 超时）。
* ``sleep``：no-op 异步函数，使默认 10 秒重试间隔不真实等待。
* ``logger``：测试内新建的专用 :class:`logging.Logger`，挂载一个把
  :class:`logging.LogRecord` 收进列表的 handler，用于断言最终的 ERROR 失败日志。
* 默认 ``max_retries=2`` -> 累计发送尝试 == 3。

「提交记录不回滚」的建模：在调用 ``notify_submission`` 之前，于一份全新的内存
SQLite 中创建完整关联链（Teacher、Class、Course、Assignment、Student）并经
``repo.create_submission(...)`` 写入并提交一条真实的 Submission 行（其主键 ==
生成的 ``submission_id``）；调用结束后，用一份**全新会话**从数据库重新读取该行，
断言其仍然存在且字段未被篡改——faithfully 验证「不回滚」。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.adapters.email_service import EmailService, SubmissionRecord
from app.db import create_all, create_db_engine, create_session_factory
from app.models import Submission
from app.repository import Repository

# 固定的有效截止时间，仅用于满足 Assignment 行的非空字段（与被测属性无关）。
_FIXED_DEADLINE = datetime(2099, 1, 1, 0, 0, 0)

# 非空白文本：保证邮箱在 ``student_email.strip()`` 后非空，从而触发实际发送流程，
# 同时也用于 submission_id（作为主键，需非空）、标题与文件名。
_non_blank_text = st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != "")


class _CountingFailingSender:
    """始终失败的异步「单次发送」fake，并统计调用次数。

    ``mode == "timeout"`` 时抛 :class:`asyncio.TimeoutError`（模拟需求 11.4 的发送
    超时路径）；否则抛普通 :class:`RuntimeError`（模拟一般发送异常路径）。两条路径
    都应被 ``notify_submission`` 捕获并按调度重试，最终均不向调用方抛出。
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    async def __call__(self, recipient: str, body: str) -> None:
        self.calls += 1
        if self.mode == "timeout":
            raise asyncio.TimeoutError()
        raise RuntimeError("SMTP 连接失败（fake）")


class _ListHandler(logging.Handler):
    """把所有 :class:`logging.LogRecord` 收进列表的 handler，便于断言日志内容。"""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - 简单收集
        self.records.append(record)


async def _noop_sleep(_seconds: float) -> None:
    """no-op 异步休眠：使默认 10 秒重试间隔不真实等待。"""
    return None


@pytest.mark.property
@settings(max_examples=100)
@given(
    submission_id=_non_blank_text,
    email=_non_blank_text,
    assignment_title=_non_blank_text,
    file_name=_non_blank_text,
    submitted_at=st.datetimes(),
    failure_mode=st.sampled_from(["exception", "timeout"]),
)
def test_email_final_failure_keeps_submission_and_does_not_raise(
    submission_id: str,
    email: str,
    assignment_title: str,
    file_name: str,
    submitted_at: datetime,
    failure_mode: str,
) -> None:
    """邮箱非空但 3 次发送全失败：notify_submission 不抛出、记 ERROR 日志，且提交行仍在。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session_factory = create_session_factory(engine)
    setup_session = session_factory()
    try:
        repo = Repository(setup_session)

        # 创建完整关联链并写入一条真实的 Submission 行（主键 == submission_id），提交。
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
                allowed_extensions=[".pdf"],
                deadline=_FIXED_DEADLINE,
            )
            student = repo.create_user(
                role="Student",
                account="student-acct",
                student_id="stu-1",
                class_id=clazz.id,
            )
            repo.create_submission(
                id=submission_id,
                student_id=student.id,
                assignment_id=assignment.id,
                file_name=file_name,
                storage_id="obj-1",
                submitted_at=submitted_at,
            )

        # 专用 logger + 捕获 handler（断言最终 ERROR 失败日志）。
        captured = _ListHandler()
        test_logger = logging.getLogger(f"test_prop36.{id(captured)}")
        test_logger.setLevel(logging.DEBUG)
        test_logger.propagate = False
        test_logger.addHandler(captured)

        sender = _CountingFailingSender(failure_mode)
        service = EmailService(
            sender,
            sleep=_noop_sleep,
            logger=test_logger,
            # 保持默认 max_retries=2 -> 累计 3 次尝试。
        )

        record = SubmissionRecord(
            submission_id=submission_id,
            assignment_title=assignment_title,
            submitted_at=submitted_at,
            file_name=file_name,
        )

        try:
            # (a) 正常返回 None 且不抛出（若抛出，asyncio.run 会向上传播使测试失败）。
            result = asyncio.run(service.notify_submission(record, email))
            assert result is None
        finally:
            test_logger.removeHandler(captured)

        # (b) sender 恰好被调用 3 次（1 次首发 + 2 次重试）。
        assert sender.calls == 3, f"应累计尝试 3 次发送，实际 {sender.calls} 次"

        # (c) 至少一条 ERROR 级别日志，其消息同时包含 submission_id（提交记录标识）。
        error_messages = [
            r.getMessage() for r in captured.records if r.levelno == logging.ERROR
        ]
        assert error_messages, "全部尝试失败后应记录一条 ERROR 级别的发送失败日志"
        assert any(submission_id in msg for msg in error_messages), (
            "失败日志应包含提交记录标识 submission_id"
        )

        # (d) 提交行仍存在且未被篡改——用全新会话从库中重新读取，验证「不回滚」。
        verify_session = session_factory()
        try:
            stored = verify_session.get(Submission, submission_id)
            assert stored is not None, "邮件最终失败不应导致提交记录被回滚/删除"
            assert stored.id == submission_id
            assert stored.file_name == file_name
            assert stored.submitted_at == submitted_at
        finally:
            verify_session.close()
    finally:
        setup_session.close()
        engine.dispose()
