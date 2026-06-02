# Feature: homework-upload-system, Property 35: 邮件重试调度
"""Property 35：邮件重试调度（design.md「Correctness Properties」）。

纯函数 :func:`app.adapters.email_service.next_attempt_schedule` 的语义
（需求 11.5）：

*For any* 配置（默认最多重试 2 次、间隔 10 秒）：

* ``max_retries <= 0`` 时返回空列表 ``[]``（不重试，仅首次发送）；
* ``max_retries > 0`` 时，返回的重试计划长度等于 ``max_retries``、每项均等于
  配置的 ``interval_seconds``，且累计发送尝试次数 = ``max_retries + 1``（默认 ≤ 3）。

**Validates: Requirements 11.5**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.adapters.email_service import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_INTERVAL_SECONDS,
    next_attempt_schedule,
)


def test_default_call_schedule_and_total_attempts() -> None:
    """默认调用：next_attempt_schedule() == [10, 10] 且累计尝试 == 3（<= 3）。"""
    schedule = next_attempt_schedule()
    assert schedule == [10, 10]

    total_attempts = len(schedule) + 1
    assert total_attempts == 3
    assert total_attempts <= 3
    # 与默认常量保持一致：长度 == 默认最大重试次数、首次+重试 == max_retries+1。
    assert len(schedule) == DEFAULT_MAX_RETRIES
    assert total_attempts == DEFAULT_MAX_RETRIES + 1


@pytest.mark.property
@settings(max_examples=100)
@given(
    # 覆盖 0、负数与较小正数（1..5），并叠加默认值附近的边界。
    max_retries=st.integers(min_value=-5, max_value=5),
    interval_seconds=st.integers(min_value=1, max_value=60),
)
def test_retry_schedule_length_interval_and_total_attempts(
    max_retries: int, interval_seconds: int
) -> None:
    """重试计划满足长度/间隔/累计尝试次数约束（需求 11.5）。"""
    schedule = next_attempt_schedule(
        max_retries=max_retries, interval_seconds=interval_seconds
    )

    if max_retries <= 0:
        # 不重试：仅首次发送，重试计划为空。
        assert schedule == []
        # 累计发送尝试次数 = 重试次数 + 1（首次发送）= 1。
        assert len(schedule) + 1 == 1
        return

    # 重试次数 > 0：长度等于 max_retries。
    assert len(schedule) == max_retries
    # 每项延迟等于配置的固定间隔。
    assert all(delay == interval_seconds for delay in schedule)
    # 累计发送尝试次数 = 重试次数 + 1（首次发送）。
    total_attempts = len(schedule) + 1
    assert total_attempts == max_retries + 1


@pytest.mark.property
@settings(max_examples=100)
@given(interval_seconds=st.integers(min_value=1, max_value=60))
def test_default_max_retries_total_attempts_within_three(
    interval_seconds: int,
) -> None:
    """使用默认最大重试次数时，累计发送尝试次数恒等于 3（<= 3）。"""
    schedule = next_attempt_schedule(interval_seconds=interval_seconds)

    assert len(schedule) == DEFAULT_MAX_RETRIES
    assert all(delay == interval_seconds for delay in schedule)

    total_attempts = len(schedule) + 1
    assert total_attempts == 3
    assert total_attempts <= 3
    # 默认间隔常量为 10s（需求 11.5）。
    assert DEFAULT_RETRY_INTERVAL_SECONDS == 10
