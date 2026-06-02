# Feature: homework-upload-system, Property 27: 文件扩展名不区分大小写校验
"""Property 27：文件扩展名不区分大小写校验（design.md「Correctness Properties」）。

*For any* 文件名与作业允许扩展名集合，:func:`app.core.validators.validate_extension`
通过当且仅当文件名扩展名（忽略大小写、取最后一个点号之后的部分）属于允许集合；
不属于时提交被拒绝并返回“扩展名不被允许错误”
（:attr:`app.core.errors.ErrorCode.EXTENSION_NOT_ALLOWED`）。

实现语义（来自 validators.py）：使用 :func:`os.path.splitext` 提取扩展名，去除
前导点号并转小写后与允许集合比较；无扩展名（如 ``"report"``）或仅以点号开头的
隐藏文件形式（如 ``".pdf"``）均视为“无扩展名”从而被拒绝。本测试因此始终生成
**非空基础名 + 一个点号 + 扩展名** 的合法文件名形态，使大小写不敏感成为被检验的
核心性质。

**Validates: Requirements 9.4**
"""

from __future__ import annotations

import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.core.validators import ALLOWED_EXTENSIONS, validate_extension

# 允许扩展名（小写）列表，供采样使用。
_ALLOWED_LIST = sorted(ALLOWED_EXTENSIONS)
# 允许扩展名的小写集合，用于负例过滤判定。
_ALLOWED_LOWER = {e.lower() for e in ALLOWED_EXTENSIONS}

# 基础名字母表：仅含 ASCII 字母、数字、下划线与连字符（不含点号与路径分隔符），
# 确保 os.path.splitext 提取到的扩展名就是我们拼接的那一段。
_BASE_ALPHABET = string.ascii_letters + string.digits + "_-"
_base_name = st.text(alphabet=_BASE_ALPHABET, min_size=1, max_size=24)


@st.composite
def _cased_allowed_extension(draw: st.DrawFn) -> str:
    """从允许集合采样一个扩展名，并对每个字符随机施加大小写变换。

    例如对 ``"pdf"`` 可生成 ``"PDF"`` / ``"Pdf"`` / ``"pDf"`` 等；数字字符
    （如 ``"7z"`` 中的 ``"7"``）大小写变换后保持不变。
    """
    ext = draw(st.sampled_from(_ALLOWED_LIST))
    return "".join(ch.upper() if draw(st.booleans()) else ch for ch in ext)


# 负例扩展名：任意非空 ASCII 字母数字串，其小写形态不属于允许集合。
_disallowed_extension = st.text(
    alphabet=string.ascii_letters + string.digits, min_size=1, max_size=10
).filter(lambda e: e.lower() not in _ALLOWED_LOWER)


@pytest.mark.property
@settings(max_examples=100)
@given(base=_base_name, ext=_cased_allowed_extension())
def test_allowed_extension_passes_regardless_of_case(base: str, ext: str) -> None:
    """允许扩展名（任意大小写组合）恒通过校验，且不携带错误码。"""
    filename = f"{base}.{ext}"
    result = validate_extension(filename, ALLOWED_EXTENSIONS)

    assert result.ok is True
    assert result.error_code is None


@pytest.mark.property
@settings(max_examples=100)
@given(base=_base_name, ext=_disallowed_extension)
def test_disallowed_extension_fails_with_extension_not_allowed(
    base: str, ext: str
) -> None:
    """扩展名不属于允许集合（忽略大小写）时，被拒绝并返回 EXTENSION_NOT_ALLOWED。"""
    filename = f"{base}.{ext}"
    result = validate_extension(filename, ALLOWED_EXTENSIONS)

    assert result.ok is False
    assert result.error_code is ErrorCode.EXTENSION_NOT_ALLOWED


@pytest.mark.property
@settings(max_examples=100)
@given(base=_base_name, ext=st.sampled_from(_ALLOWED_LIST))
def test_case_insensitivity_is_consistent_across_all_casings(
    base: str, ext: str
) -> None:
    """同一扩展名的全小写、全大写与标题大小写三种形态判定结果一致（均通过）。"""
    lower = validate_extension(f"{base}.{ext.lower()}", ALLOWED_EXTENSIONS)
    upper = validate_extension(f"{base}.{ext.upper()}", ALLOWED_EXTENSIONS)
    title = validate_extension(f"{base}.{ext.capitalize()}", ALLOWED_EXTENSIONS)

    assert lower.ok is True
    assert upper.ok is True
    assert title.ok is True
