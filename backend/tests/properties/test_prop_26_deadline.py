# Feature: homework-upload-system, Property 26: 截止时间边界
"""Property 26：截止时间边界（design.md「Correctness Properties」）。

*For any* 截止时间 ``deadline`` 与当前时间 ``now``，纯函数
:func:`app.core.validators.validate_deadline` 通过当且仅当 ``deadline > now``；
否则返回携带 :attr:`app.core.errors.ErrorCode.INVALID_DEADLINE` 的失败结果。

该边界同时支配两处业务规则：作业创建在 ``deadline <= now`` 时拒绝（需求 8.13），
作业提交在 ``now > deadline`` 时拒绝（需求 9.6）——二者由同一时间边界判定。
等号情形（``deadline == now``）必须被拒绝。

使用 Hypothesis 的 ``datetimes()`` 策略生成 ``deadline`` 与 ``now``，覆盖
``deadline > now``、``deadline == now``、``deadline < now`` 三类关系。

**Validates: Requirements 8.13, 9.6**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.core.validators import validate_deadline


@pytest.mark.property
@settings(max_examples=100)
@given(deadline=st.datetimes(), now=st.datetimes())
def test_validate_deadline_iff_after_now(deadline, now) -> None:
    """validate_deadline 通过 当且仅当 deadline > now；失败携带 INVALID_DEADLINE。"""
    result = validate_deadline(deadline, now)

    assert result.ok == (deadline > now)
    if result.ok:
        assert result.error_code is None
    else:
        # deadline <= now（含等号与早于）必须以截止时间无效错误拒绝。
        assert result.error_code is ErrorCode.INVALID_DEADLINE


@pytest.mark.property
@settings(max_examples=100)
@given(instant=st.datetimes())
def test_validate_deadline_equal_is_rejected(instant) -> None:
    """显式边界：deadline == now 必须被拒绝并携带 INVALID_DEADLINE。"""
    result = validate_deadline(instant, instant)

    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_DEADLINE
