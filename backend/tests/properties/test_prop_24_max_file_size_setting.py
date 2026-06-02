# Feature: homework-upload-system, Property 24: 最大文件大小取值校验
"""Property 24: 最大文件大小取值校验。

依据 design.md「Correctness Properties」Property 24：

    *For any* 最大文件大小取值，:func:`validate_max_file_size_setting` 通过
    当且仅当其为 ``1..100``（含端点）之间的正数（整数值）；否则返回
    “最大文件大小取值无效错误”（:attr:`ErrorCode.INVALID_MAX_FILE_SIZE`）。

实现语义补充（见 validators.validate_max_file_size_setting docstring）：

* ``None`` -> 视为合法（创建时归一化为默认 5MB）；
* ``bool`` 被拒绝（避免 ``True/False`` 被当作 ``1/0``）；
* 含小数部分的 ``float`` 被拒绝；取整数值的 ``float`` 在范围内被接受；
* 越界（不在 ``[1, 100]``）被拒绝。

**Validates: Requirements 8.11**
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.core.validators import (
    MAX_FILE_SIZE_MB,
    MIN_FILE_SIZE_MB,
    validate_max_file_size_setting,
)


def _expected_ok(max_mb: object) -> bool:
    """以独立于实现的方式复刻 Property 24 的预期判定。

    与实现语义保持一致：``None`` 合法；``bool`` 非法；非数值非法；
    含小数的 float 非法；整数值（含整数值 float）落在 ``[1, 100]`` 合法。
    """
    if max_mb is None:
        return True
    # bool 是 int 的子类，必须先于数值判断排除。
    if isinstance(max_mb, bool) or not isinstance(max_mb, (int, float)):
        return False
    if isinstance(max_mb, float):
        if not math.isfinite(max_mb) or not max_mb.is_integer():
            return False
    return MIN_FILE_SIZE_MB <= int(max_mb) <= MAX_FILE_SIZE_MB


# 覆盖输入空间：越界整数（0、负数、>100）、范围内整数、None、各类 float
# （整数值 float、含小数 float、NaN/Inf），以及非数值类型。
_max_mb_strategy = st.one_of(
    st.none(),
    st.integers(min_value=-50, max_value=200),       # 含 0、负数、>100 及范围内整数
    st.integers(min_value=1, max_value=100),         # 加密范围内取样密度
    st.booleans(),                                   # bool 必须被拒绝
    st.floats(min_value=-10.0, max_value=200.0),     # 整数值 + 含小数 float
    st.floats(allow_nan=True, allow_infinity=True),  # NaN / Inf 等非有限值
    st.text(max_size=5),                             # 非数值类型
)


@pytest.mark.property
@settings(max_examples=100)
@given(max_mb=_max_mb_strategy)
def test_validate_max_file_size_setting_iff_in_range(max_mb: object) -> None:
    """通过当且仅当取值为 [1,100] 内的整数值（或 None）；否则 INVALID_MAX_FILE_SIZE。"""
    result = validate_max_file_size_setting(max_mb)
    expected = _expected_ok(max_mb)

    assert result.ok is expected

    if expected:
        # 通过时不应携带错误码。
        assert result.error_code is None
    else:
        # 失败时必须携带 INVALID_MAX_FILE_SIZE。
        assert result.error_code is ErrorCode.INVALID_MAX_FILE_SIZE


@pytest.mark.property
@settings(max_examples=100)
@given(value=st.integers(min_value=MIN_FILE_SIZE_MB, max_value=MAX_FILE_SIZE_MB))
def test_in_range_integers_always_pass(value: int) -> None:
    """[1,100] 内的整数恒通过校验且不带错误码。"""
    result = validate_max_file_size_setting(value)
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.property
@settings(max_examples=100)
@given(
    value=st.one_of(
        st.integers(max_value=MIN_FILE_SIZE_MB - 1),   # <= 0 及其它 < 1
        st.integers(min_value=MAX_FILE_SIZE_MB + 1),    # > 100
    )
)
def test_out_of_range_integers_always_fail(value: int) -> None:
    """落在 [1,100] 之外的整数恒返回 INVALID_MAX_FILE_SIZE。"""
    result = validate_max_file_size_setting(value)
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_MAX_FILE_SIZE


def test_boundary_and_none_cases() -> None:
    """显式边界覆盖：None、下界、上界通过；越界与含小数 float 失败。"""
    assert validate_max_file_size_setting(None).ok is True
    assert validate_max_file_size_setting(MIN_FILE_SIZE_MB).ok is True   # 1 -> 通过
    assert validate_max_file_size_setting(MAX_FILE_SIZE_MB).ok is True   # 100 -> 通过
    assert validate_max_file_size_setting(float(MAX_FILE_SIZE_MB)).ok is True  # 100.0 -> 通过

    assert validate_max_file_size_setting(0).ok is False                # 下界 -1
    assert validate_max_file_size_setting(MAX_FILE_SIZE_MB + 1).ok is False  # 上界 +1
    assert validate_max_file_size_setting(5.5).ok is False              # 含小数 -> 失败
    assert validate_max_file_size_setting(True).ok is False             # bool -> 失败
