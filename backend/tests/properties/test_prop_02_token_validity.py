"""属性测试：Property 2 - 令牌有效性以过期时刻为界。

依据 design.md「Correctness Properties」Property 2 与需求 1.4。
被测对象：:func:`app.core.validators.is_token_valid`。
"""

# Feature: homework-upload-system, Property 2: 令牌有效性以过期时刻为界

from __future__ import annotations

from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.validators import is_token_valid


@pytest.mark.property
@settings(max_examples=100)
@given(expiry=st.datetimes(), now=st.datetimes())
def test_token_validity_bounded_by_expiry(expiry: datetime, now: datetime) -> None:
    """对任意 expiry 与 now，is_token_valid 返回真当且仅当 now < expiry。

    通过独立生成两个 datetime，覆盖 now < expiry、now == expiry、now > expiry
    三类关系；Hypothesis 也会刻意尝试相等/接近的边界值。

    **Validates: Requirements 1.4**
    """
    assert is_token_valid(expiry, now) == (now < expiry)


@pytest.mark.property
@settings(max_examples=100)
@given(boundary=st.datetimes())
def test_token_invalid_exactly_at_expiry(boundary: datetime) -> None:
    """边界情形：now == expiry 时令牌应判为无效（过期时刻为开区间上界）。

    **Validates: Requirements 1.4**
    """
    assert is_token_valid(boundary, boundary) is False
