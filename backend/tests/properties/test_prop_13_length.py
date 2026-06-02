# Feature: homework-upload-system, Property 13: 字段长度上限校验
"""Property 13：字段长度上限校验（design.md「Correctness Properties」）。

*For any* 受长度约束的字段值与上限 ``max_len``，纯函数
:func:`app.core.validators.validate_length` 返回 ``True`` 当且仅当
``len(value) <= max_len``。系统中受约束的字段及其上限为：

* 班级 school / grade / major ≤ 20（需求 5.4 / 5.5 / 5.6）
* 课程 name ≤ 20（需求 7.4）
* 作业 title ≤ 20（需求 8.6）
* 作业 content ≤ 100（需求 8.7）

**Validates: Requirements 5.4, 5.5, 5.6, 7.4, 8.6, 8.7**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.validators import validate_length

# 业务中实际使用的字段长度上限（design.md Property 13）。
FIELD_MAX_LENGTHS = [20, 100]


@pytest.mark.property
@settings(max_examples=100)
@given(
    # 生成长度环绕各上限边界的字符串（0..120 覆盖 20/100 两侧）。
    value=st.text(max_size=120),
    # 覆盖业务实际上限，并叠加一段较小区间以增加边界附近的取样密度。
    max_len=st.one_of(
        st.sampled_from(FIELD_MAX_LENGTHS),
        st.integers(min_value=0, max_value=120),
    ),
)
def test_validate_length_iff_within_limit(value: str, max_len: int) -> None:
    """validate_length(value, max_len) 为真 当且仅当 len(value) <= max_len。"""
    assert validate_length(value, max_len) == (len(value) <= max_len)


@pytest.mark.property
@settings(max_examples=100)
@given(
    max_len=st.sampled_from(FIELD_MAX_LENGTHS),
    # 用单一字符重复，确保字符长度可被精确控制至边界。
    fill_char=st.characters(min_codepoint=33, max_codepoint=126),
)
def test_validate_length_boundary(max_len: int, fill_char: str) -> None:
    """显式边界覆盖：恰为上限通过、上限 +1 失败、上限 -1 通过。"""
    at_limit = fill_char * max_len
    over_limit = fill_char * (max_len + 1)
    under_limit = fill_char * (max_len - 1)

    assert validate_length(at_limit, max_len) is True  # len == max_len -> 通过
    assert validate_length(over_limit, max_len) is False  # len == max_len + 1 -> 失败
    assert validate_length(under_limit, max_len) is True  # len < max_len -> 通过
