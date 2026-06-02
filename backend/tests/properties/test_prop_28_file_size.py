# Feature: homework-upload-system, Property 28: 文件大小校验
"""Property 28：文件大小校验（design.md「Correctness Properties」）。

*For any* 文件字节大小 ``size`` 与作业最大大小 ``max_mb``，纯函数
:func:`app.core.validators.validate_file_size` 通过校验（``result.ok is True``）
当且仅当 ``0 < size <= max_mb * 1024 * 1024``。

错误码语义（validators.py / 需求 9.3、9.5）：

* ``size <= 0`` -> :attr:`ErrorCode.EMPTY_FILE`（文件为空）；
* ``size > max_mb * 1024 * 1024`` -> :attr:`ErrorCode.FILE_TOO_LARGE`（文件超过大小限制）；
* 其余（``0 < size <= 上限``）-> 通过。

**Validates: Requirements 9.5**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.core.validators import validate_file_size


def _max_bytes(max_mb: int) -> int:
    """作业最大大小（MB）对应的字节上限。"""
    return max_mb * 1024 * 1024


# 作业最大文件大小的取值区间（MB）：业务允许 1..100（需求 8.11）。
max_mb_strategy = st.integers(min_value=1, max_value=100)


def _size_bytes_strategy(max_mb: int) -> st.SearchStrategy[int]:
    """生成环绕给定上限边界的字节大小取值。

    覆盖：负值、0、小正值、上限附近（上限 ±2）、以及远超上限的大值，
    以便对“通过 / 为空 / 超限”三类分支充分取样。
    """
    limit = _max_bytes(max_mb)
    return st.one_of(
        st.integers(min_value=-1024, max_value=-1),  # 负值 -> EMPTY_FILE
        st.just(0),  # 0 字节 -> EMPTY_FILE
        st.integers(min_value=1, max_value=4096),  # 小正值 -> 通常通过
        st.integers(min_value=limit - 2, max_value=limit + 2),  # 紧贴上限边界
        st.integers(min_value=limit + 1, max_value=limit * 2 + 1),  # 明显超限
    )


@pytest.mark.property
@settings(max_examples=100)
@given(data=st.data(), max_mb=max_mb_strategy)
def test_validate_file_size_iff_within_limit(data: st.DataObject, max_mb: int) -> None:
    """validate_file_size 通过 当且仅当 0 < size <= max_mb * 1024 * 1024。

    并断言失败分支的具体错误码：
    ``size <= 0`` -> EMPTY_FILE；超限 -> FILE_TOO_LARGE。
    """
    size_bytes = data.draw(_size_bytes_strategy(max_mb))
    result = validate_file_size(size_bytes, max_mb)

    expected_ok = 0 < size_bytes <= _max_bytes(max_mb)
    assert result.ok is expected_ok

    if expected_ok:
        assert result.error_code is None
    elif size_bytes <= 0:
        assert result.error_code is ErrorCode.EMPTY_FILE
    else:  # size_bytes > max_bytes
        assert result.error_code is ErrorCode.FILE_TOO_LARGE


@pytest.mark.property
@settings(max_examples=100)
@given(max_mb=max_mb_strategy)
def test_validate_file_size_boundary(max_mb: int) -> None:
    """显式边界覆盖：恰为上限通过、上限 +1 失败（FILE_TOO_LARGE）。

    同时覆盖 1 字节（最小有效）通过与 0 字节（为空）失败。
    """
    limit = _max_bytes(max_mb)

    # size == max_bytes -> 通过
    at_limit = validate_file_size(limit, max_mb)
    assert at_limit.ok is True
    assert at_limit.error_code is None

    # size == max_bytes + 1 -> 失败，FILE_TOO_LARGE
    over_limit = validate_file_size(limit + 1, max_mb)
    assert over_limit.ok is False
    assert over_limit.error_code is ErrorCode.FILE_TOO_LARGE

    # size == 1 -> 最小有效字节，通过
    min_valid = validate_file_size(1, max_mb)
    assert min_valid.ok is True
    assert min_valid.error_code is None

    # size == 0 -> 文件为空，EMPTY_FILE
    empty = validate_file_size(0, max_mb)
    assert empty.ok is False
    assert empty.error_code is ErrorCode.EMPTY_FILE
