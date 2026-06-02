# Feature: homework-upload-system, Property 23: 允许扩展名集合校验
"""Property 23：允许扩展名集合校验（design.md「Correctness Properties」）。

*For any* 扩展名集合 ``exts``，纯函数
:func:`app.core.validators.validate_allowed_extension_set` 通过当且仅当
该集合 **非空** 且为 :data:`app.core.validators.ALLOWED_EXTENSIONS`
（``{md, pdf, docx, zip, rar, 7z}``）的子集：

* 空集合 -> 失败，携带 :attr:`ErrorCode.NO_EXTENSION_SELECTED`（需求 8.9）；
* 非空但含越界取值（非子集）-> 失败，携带
  :attr:`ErrorCode.EXTENSION_NOT_ALLOWED`（需求 8.8）；
* 非空且为子集 -> 通过。

**Validates: Requirements 8.8, 8.9**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.core.validators import ALLOWED_EXTENSIONS, validate_allowed_extension_set

# 允许扩展名全集（排序为列表以供采样生成器使用）。
_ALLOWED_LIST = sorted(ALLOWED_EXTENSIONS)

# 越界字符串：任意文本，但显式排除恰好命中允许集合的取值，
# 确保其确实落在 ALLOWED_EXTENSIONS 之外。
_out_of_range_text = st.text().filter(lambda s: s not in ALLOWED_EXTENSIONS)

# 允许集合的任意子集（含空集）。
_subset_strategy = st.sets(st.sampled_from(_ALLOWED_LIST)).map(frozenset)


@st.composite
def _mixed_ext_sets(draw: st.DrawFn) -> frozenset[str]:
    """生成混合扩展名集合：允许子集 ∪ 任意越界字符串（含两者可空）。

    覆盖三类输入：空集、纯子集、含越界值的非子集。
    """
    subset = draw(st.sets(st.sampled_from(_ALLOWED_LIST)))
    extras = draw(st.sets(_out_of_range_text, max_size=3))
    return frozenset(subset | extras)


@pytest.mark.property
@settings(max_examples=100)
@given(exts=_mixed_ext_sets())
def test_allowed_extension_set_iff_nonempty_subset(exts: frozenset[str]) -> None:
    """通过当且仅当集合非空且为 ALLOWED_EXTENSIONS 的子集；否则携带对应错误码。"""
    result = validate_allowed_extension_set(exts)

    if not exts:
        # 空集合 -> 至少选择一种扩展名。
        assert result.ok is False
        assert result.error_code is ErrorCode.NO_EXTENSION_SELECTED
    elif set(exts) <= ALLOWED_EXTENSIONS:
        # 非空子集 -> 通过，不携带错误码。
        assert result.ok is True
        assert result.error_code is None
    else:
        # 含越界取值 -> 扩展名不被允许。
        assert result.ok is False
        assert result.error_code is ErrorCode.EXTENSION_NOT_ALLOWED


@pytest.mark.property
@settings(max_examples=100)
@given(exts=_subset_strategy.filter(lambda s: len(s) > 0))
def test_nonempty_subset_passes(exts: frozenset[str]) -> None:
    """任意非空的允许子集恒通过校验。"""
    result = validate_allowed_extension_set(exts)
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.property
@settings(max_examples=100)
@given(
    subset=_subset_strategy,
    extras=st.sets(_out_of_range_text, min_size=1, max_size=3),
)
def test_set_with_out_of_range_rejected(
    subset: frozenset[str], extras: frozenset[str]
) -> None:
    """含至少一个越界取值的非空集合 -> 失败且携带 EXTENSION_NOT_ALLOWED。"""
    exts = frozenset(set(subset) | set(extras))
    result = validate_allowed_extension_set(exts)
    assert result.ok is False
    assert result.error_code is ErrorCode.EXTENSION_NOT_ALLOWED


@pytest.mark.property
@settings(max_examples=100)
@given(_dummy=st.just(None))
def test_empty_set_returns_no_extension_selected(_dummy: None) -> None:
    """空集合 -> 失败且携带 NO_EXTENSION_SELECTED。"""
    result = validate_allowed_extension_set(frozenset())
    assert result.ok is False
    assert result.error_code is ErrorCode.NO_EXTENSION_SELECTED
