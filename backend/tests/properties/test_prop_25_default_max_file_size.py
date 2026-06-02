# Feature: homework-upload-system, Property 25: 最大文件大小默认值
"""Property 25：最大文件大小默认值（design.md「Correctness Properties」）。

纯函数 :func:`app.core.validators.normalize_max_file_size` 的归一化语义
（需求 8.10）：

* 未指定（``None``）时返回默认值 :data:`DEFAULT_FILE_SIZE_MB`（5MB）；
* 指定了合法取值（``1..100`` 间的整数值）时按原值返回为 ``int``。

**Validates: Requirements 8.10**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.validators import DEFAULT_FILE_SIZE_MB, normalize_max_file_size


def test_normalize_none_returns_default() -> None:
    """未指定（None）时归一化为默认值 5MB（DEFAULT_FILE_SIZE_MB）。"""
    assert normalize_max_file_size(None) == DEFAULT_FILE_SIZE_MB
    assert DEFAULT_FILE_SIZE_MB == 5


@pytest.mark.property
@settings(max_examples=100)
@given(value=st.integers(min_value=1, max_value=100))
def test_normalize_provided_value_returns_int_value(value: int) -> None:
    """指定合法取值时按原值返回为 int：normalize_max_file_size(v) == int(v)。"""
    assert normalize_max_file_size(value) == int(value)
