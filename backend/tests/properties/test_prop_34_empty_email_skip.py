# Feature: homework-upload-system, Property 34: 空邮箱跳过发送并记录日志
"""Property 34：空邮箱跳过发送并记录日志（design.md「Correctness Properties」）。

*For any* 邮箱字段为空（``None`` 或仅空白字符）的提交记录，
:meth:`app.adapters.email_service.EmailService.notify_submission` 必须：

* **跳过发送**：注入的 ``sender`` 从不被调用（调用计数恒为 0）；
* **记录日志**：至少一条日志记录同时包含该提交记录标识 ``submission_id`` 与
  原因 :data:`app.adapters.email_service.EMAIL_MISSING_REASON`（"邮箱缺失"）。

测试通过构造函数注入全部副作用依赖（无需真实 SMTP / 真实等待）：

* ``sender``：异步 fake，记录调用次数；本属性下应保持为 0；
* ``sleep``：no-op 异步函数（跳过分支不触发重试，仅为隔离真实等待）；
* ``logger``：新建专用 :class:`logging.Logger`，挂载将 ``LogRecord`` 收集进列表的
  自定义 handler（每个示例独立，避免 Hypothesis 跨示例污染）。

``notify_submission`` 为协程，测试函数为同步函数并以 :func:`asyncio.run` 驱动。

**Validates: Requirements 11.3**
"""

from __future__ import annotations

import asyncio
import logging
from string import whitespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.adapters.email_service import (
    EMAIL_MISSING_REASON,
    EmailService,
    SubmissionRecord,
)


class _ListHandler(logging.Handler):
    """将每条 ``LogRecord`` 追加到内部列表的极简 handler（供断言用）。"""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _CountingSender:
    """异步 fake sender：仅统计被调用次数；本属性下应保持为 0（从不发送）。"""

    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(self, recipient: str, body: str) -> None:
        self.call_count += 1


async def _noop_sleep(_seconds: float) -> None:
    """no-op 异步休眠：跳过分支不触发重试，仅用于隔离真实等待。"""
    return None


# 仅空白字符（含各种 Unicode 空白）的非空字符串，去除首尾空白后仍为空。
_blank_whitespace = st.text(alphabet=whitespace, min_size=1, max_size=8)

# 空邮箱的输入空间：None / 空串 / 仅空白字符串。
_empty_email = st.one_of(
    st.none(),
    st.just(""),
    st.just("   "),
    _blank_whitespace,
)


@pytest.mark.property
@settings(max_examples=100)
@given(
    submission_id=st.text(min_size=1, max_size=50),
    assignment_title=st.text(max_size=50),
    file_name=st.text(max_size=50),
    submitted_at=st.datetimes(),
    student_email=_empty_email,
)
def test_empty_email_skips_send_and_logs(
    submission_id: str,
    assignment_title: str,
    file_name: str,
    submitted_at,
    student_email,
) -> None:
    """空邮箱：sender 从不调用，且日志同时含 submission_id 与"邮箱缺失"。"""
    record = SubmissionRecord(
        submission_id=submission_id,
        assignment_title=assignment_title,
        submitted_at=submitted_at,
        file_name=file_name,
    )

    # 每个示例独立的 logger + handler，避免 Hypothesis 跨示例污染。
    handler = _ListHandler()
    logger = logging.getLogger(f"test_prop_34.{id(handler)}")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    sender = _CountingSender()
    service = EmailService(sender=sender, sleep=_noop_sleep, logger=logger)

    asyncio.run(service.notify_submission(record, student_email))

    # 跳过发送：注入的 sender 从未被调用。
    assert sender.call_count == 0

    # 至少一条日志记录同时包含 submission_id 与"邮箱缺失"原因。
    messages = [rec.getMessage() for rec in handler.records]
    assert any(
        (submission_id in msg) and (EMAIL_MISSING_REASON in msg) for msg in messages
    ), (
        "期望存在同时包含 submission_id 与 EMAIL_MISSING_REASON 的日志，"
        f"实际日志：{messages!r}"
    )
