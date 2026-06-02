"""Property 1: 令牌过期时间为签发后 30 分钟。

依据 design.md「Correctness Properties」Property 1 与需求 1.1：对任意签发时间
``issued_at``，``compute_token_expiry(issued_at)`` 应恰等于
``issued_at + timedelta(minutes=SESSION_TTL_MINUTES)``（即 30 分钟）。

使用 Hypothesis 的 ``datetimes()`` 策略生成任意签发时间，验证该等式恒成立。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.validators import SESSION_TTL_MINUTES, compute_token_expiry


@pytest.mark.property
@settings(max_examples=100)
@given(issued_at=st.datetimes())
def test_token_expiry_is_30_minutes_after_issuance(issued_at) -> None:
    # Feature: homework-upload-system, Property 1: 令牌过期时间为签发后 30 分钟
    # Validates: Requirements 1.1
    expected = issued_at + timedelta(minutes=SESSION_TTL_MINUTES)
    assert compute_token_expiry(issued_at) == expected
