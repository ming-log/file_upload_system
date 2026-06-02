"""邮件发送时机集成测试（任务 16.4）。

以 **mock SMTP 发送器** 与 **可控时钟/超时** 验证 :class:`EmailService` 的两条
时间相关行为，无需真实 SMTP I/O、无需真实等待：

* **需求 11.1（60 秒内发起）**：作业提交记录创建成功且邮箱非空时，
  ``Email_Service`` 应在记录创建成功后 60 秒内 *发起* 发送。本测试将「发起」
  建模为「注入的 sender 被实际调用」，并进一步断言在首次发送 *之前* 未发生任何
  休眠（``sleep`` 未被调用）—— 即发送是 *立即发起* 而非被无限期推迟，因此天然
  落在 60 秒窗口内。``EmailService.notify_submission`` 的实现确实在进入循环后
  立刻调用 ``asyncio.wait_for(sender(...))``，发送前不 sleep。

* **需求 11.4（单次发送 30 秒超时判失败）**：单次发送尝试发起后若在
  ``timeout_seconds`` 内未收到成功响应，则本次发送判为失败。生产默认
  ``timeout_seconds == 30``（见 :data:`DEFAULT_SEND_TIMEOUT_SECONDS`）。为保证
  测试快速，本测试将 ``timeout_seconds`` 设为极小值（0.05s）并注入一个 *阻塞远
  超过该超时*（``await asyncio.sleep(10)``）的 mock sender，从而让
  :func:`asyncio.wait_for` 抛出 :class:`asyncio.TimeoutError`，驱动「单次超时即
  失败 -> 按调度重试 -> 全部失败记 ERROR 日志」的判定路径。可控的 timeout 即为
  「可控时钟」：把判定阈值从生产的 30s 收缩到 0.05s，行为完全一致、判定逻辑不变。

注入策略（与 tasks 15.5 / 15.6 的属性测试一致）：

* ``sender``：异步 mock，记录调用次数与调用顺序；
* ``sleep``：no-op 异步函数，记录被请求的休眠秒数（使默认 10s 重试间隔不真实等待）；
* ``logger``：测试内新建的专用 :class:`logging.Logger`，挂载把
  :class:`logging.LogRecord` 收进列表的 handler，用于断言 WARNING / ERROR 日志。

测试为 ``async def``；项目 pytest 配置 ``asyncio_mode = "auto"``，async 测试函数
可直接运行。

Validates: Requirements 11.1, 11.4
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import pytest

from app.adapters.email_service import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_SEND_TIMEOUT_SECONDS,
    EmailService,
    SubmissionRecord,
)


# --------------------------------------------------------------------------- #
# 测试替身（mock SMTP sender / 可控 sleep / 捕获日志）                          #
# --------------------------------------------------------------------------- #


class _ListHandler(logging.Handler):
    """把所有 :class:`logging.LogRecord` 收进列表的 handler，便于断言日志内容。"""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - 简单收集
        self.records.append(record)


class _RecordingSleep:
    """no-op 异步休眠：记录每次被请求的休眠秒数，但不真实等待。

    用于（a）断言首次发送 *之前* 未发生休眠（需求 11.1：立即发起，不推迟）；
    （b）让重试间隔（默认 10s）在测试中瞬时完成，保证用例快速。
    """

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class _SuccessSpySender:
    """mock SMTP「单次发送」：立即成功，并按顺序记录每次调用。

    每次被调用时把 ``(recipient, body)`` 追加到 ``calls``，用于断言发送被 *发起*
    （需求 11.1）以及调用次数与顺序。
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, recipient: str, body: str) -> None:
        self.calls.append((recipient, body))


class _BlockingSender:
    """mock SMTP「单次发送」：阻塞远超 timeout_seconds，迫使 wait_for 超时。

    每次调用 ``await asyncio.sleep(block_seconds)``（默认 10s，远大于测试用的
    0.05s 超时），从而让 :func:`asyncio.wait_for` 抛出 :class:`asyncio.TimeoutError`，
    模拟「单次发送 30s 内未收到成功响应」的超时判失败（需求 11.4）。
    """

    def __init__(self, block_seconds: float = 10.0) -> None:
        self.block_seconds = block_seconds
        self.calls = 0

    async def __call__(self, recipient: str, body: str) -> None:
        self.calls += 1
        await asyncio.sleep(self.block_seconds)


def _make_logger(tag: str) -> tuple[logging.Logger, _ListHandler]:
    """新建一个隔离的专用 logger 与捕获 handler。"""
    handler = _ListHandler()
    logger = logging.getLogger(f"test_email_timing.{tag}.{id(handler)}")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger, handler


def _submission() -> SubmissionRecord:
    return SubmissionRecord(
        submission_id="sub-16-4",
        assignment_title="第一次作业",
        submitted_at=datetime(2024, 5, 1, 9, 30, 5),
        file_name="report.pdf",
    )


# --------------------------------------------------------------------------- #
# 需求 11.1：邮箱非空时立即发起发送（建模「60 秒内发起」）                       #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
async def test_email_send_initiated_promptly_for_non_empty_email() -> None:
    """非空邮箱：sender 被实际调用且首发前无休眠（即立即发起，落在 60s 窗口内）。

    建模说明：需求 11.1 要求「记录创建成功后 60 秒内 *发起* 发送」。我们把「发起」
    建模为「注入的 mock sender 被调用」，并断言首次成功发送 *之前* ``sleep`` 从未
    被调用 —— 即发送不被任何前置等待推迟，立即发起，因此天然满足 60 秒窗口。
    """
    sender = _SuccessSpySender()
    sleep = _RecordingSleep()
    logger, _handler = _make_logger("prompt")

    service = EmailService(sender=sender, sleep=sleep, logger=logger)

    await service.notify_submission(_submission(), "student@example.com")

    # 发起发生：mock sender 恰好被调用一次（首发即成功，无需重试）。
    assert len(sender.calls) == 1, f"应恰好发起一次发送，实际 {len(sender.calls)} 次"
    recipient, _body = sender.calls[0]
    assert recipient == "student@example.com"

    # 首次发送之前未发生任何休眠：发送被立即发起、未被推迟（需求 11.1）。
    # 成功路径下不进入重试分支，因此整个流程不应有任何 sleep 调用。
    assert sleep.calls == [], (
        f"首次发送前不应有休眠（发送应立即发起），实际 sleep 调用：{sleep.calls!r}"
    )


# --------------------------------------------------------------------------- #
# 需求 11.4：单次发送超时（生产默认 30s）判为失败                               #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
async def test_single_attempt_timeout_judged_as_failure_and_retries() -> None:
    """单次发送超时即判失败：记 WARNING 超时日志、按调度重试、最终记 ERROR，不抛出。

    建模说明：生产默认 ``timeout_seconds == 30``（:data:`DEFAULT_SEND_TIMEOUT_SECONDS`）。
    为快速验证「单次发送在超时阈值内未完成即判失败」的判定逻辑，这里把可控时钟
    （超时阈值）收缩为 0.05s，并注入一个阻塞 10s 的 mock sender，使每次
    :func:`asyncio.wait_for` 都超时（``asyncio.TimeoutError``）。判定逻辑与 30s 时
    完全一致，仅阈值不同。
    """
    # 真实生产默认即为 30 秒；此处仅断言以记录该事实（便于阅读与回归）。
    assert DEFAULT_SEND_TIMEOUT_SECONDS == 30

    sender = _BlockingSender(block_seconds=10.0)
    sleep = _RecordingSleep()
    logger, handler = _make_logger("timeout")

    service = EmailService(
        sender=sender,
        sleep=sleep,
        logger=logger,
        timeout_seconds=0.05,  # 可控时钟：把 30s 阈值收缩到 0.05s 以加速。
        # 保持默认 max_retries=2 -> 累计 3 次尝试。
    )

    # 不抛出：notify_submission 对发送侧错误一律不向调用方传播（需求 11.6）。
    result = await service.notify_submission(_submission(), "student@example.com")
    assert result is None

    expected_attempts = DEFAULT_MAX_RETRIES + 1  # 1 次首发 + 2 次重试 = 3。

    # 每次尝试都因超时被判失败：sender 被尝试了「首发 + 重试」总次数。
    assert sender.calls == expected_attempts, (
        f"超时应被判为失败并按调度重试，应累计 {expected_attempts} 次尝试，"
        f"实际 {sender.calls} 次"
    )

    messages = [(r.levelno, r.getMessage()) for r in handler.records]

    # 每次超时都记录一条 WARNING 级别、提及「超时」的日志（单次判失败的证据）。
    warning_timeout = [
        msg
        for level, msg in messages
        if level == logging.WARNING and "超时" in msg
    ]
    assert len(warning_timeout) == expected_attempts, (
        "每次单次发送超时都应记录一条 WARNING 超时日志，"
        f"期望 {expected_attempts} 条，实际：{warning_timeout!r}"
    )

    # 最终（全部尝试均失败后）记录一条 ERROR 级别、含 submission_id 的失败日志。
    error_messages = [
        msg for level, msg in messages if level == logging.ERROR
    ]
    assert error_messages, "全部超时失败后应记录一条 ERROR 级别的发送失败日志"
    assert any("sub-16-4" in msg for msg in error_messages), (
        "最终失败日志应包含提交记录标识 submission_id"
    )

    # 重试间隔使用注入的 no-op sleep（默认 10s），共 2 次（重试次数），测试因此瞬时完成。
    assert sleep.calls == [10, 10], (
        f"重试间隔应使用注入的 sleep（默认 10s）且仅在重试间隔发生，实际：{sleep.calls!r}"
    )
