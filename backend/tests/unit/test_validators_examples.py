"""validators 纯函数的示例 / 边界单元测试。

与属性测试（tests/properties/）互补：本文件以**具体示例与边界值**覆盖
``app.core.validators`` 中各校验函数的关键临界点，例如长度恰为上限 / 超 1、
缺省最大文件大小归一化、非法邮箱示例等。

来源依据：
- 需求 2.5（邮箱“本地名@域名”格式）-> validate_email
- 需求 8.10（未指定最大文件大小默认 5 MB）-> normalize_max_file_size
- design.md「单元测试（示例 / 边界 / 错误）」：长度恰为上限 / 超 1 的字段。
"""

from __future__ import annotations

import pytest

from app.core.errors import ErrorCode
from app.core.validators import (
    ALLOWED_EXTENSIONS,
    DEFAULT_FILE_SIZE_MB,
    normalize_max_file_size,
    validate_email,
    validate_extension,
    validate_length,
    validate_max_file_size_setting,
    validate_required,
    validate_role,
)


# --------------------------------------------------------------------------- #
# validate_length —— 长度恰为上限通过、超 1 失败（上限 20 与 100 两组）          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("max_len", [20, 100])
def test_validate_length_at_limit_passes(max_len: int) -> None:
    """长度恰好等于上限应通过（len == max_len）。"""
    assert validate_length("a" * max_len, max_len) is True


@pytest.mark.unit
@pytest.mark.parametrize("max_len", [20, 100])
def test_validate_length_one_over_limit_fails(max_len: int) -> None:
    """长度超过上限 1 个字符应失败（len == max_len + 1）。"""
    assert validate_length("a" * (max_len + 1), max_len) is False


@pytest.mark.unit
@pytest.mark.parametrize("max_len", [20, 100])
def test_validate_length_below_and_empty_pass(max_len: int) -> None:
    """远低于上限及空字符串（长度 0）均应通过。"""
    assert validate_length("a" * (max_len - 1), max_len) is True
    assert validate_length("", max_len) is True


@pytest.mark.unit
def test_validate_length_none_treated_as_empty() -> None:
    """None 视作空字符串（长度 0），不超过任何非负上限。"""
    assert validate_length(None, 20) is True  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# normalize_max_file_size —— 缺省归一化为默认 5MB（需求 8.10），有值保留          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_normalize_max_file_size_none_uses_default() -> None:
    """未指定（None）时归一化为默认 5MB（需求 8.10）。"""
    assert normalize_max_file_size(None) == DEFAULT_FILE_SIZE_MB
    assert DEFAULT_FILE_SIZE_MB == 5


@pytest.mark.unit
@pytest.mark.parametrize("provided", [1, 5, 50, 100])
def test_normalize_max_file_size_keeps_provided_value(provided: int) -> None:
    """已提供取值应原样保留（转为整数 MB）。"""
    assert normalize_max_file_size(provided) == provided


# --------------------------------------------------------------------------- #
# validate_max_file_size_setting —— 边界 None/1/100 通过；0/101/-5 失败          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, 1, 100])
def test_validate_max_file_size_setting_valid(value) -> None:
    """None（缺省）、下限 1、上限 100 均应通过。"""
    result = validate_max_file_size_setting(value)
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, 101, -5])
def test_validate_max_file_size_setting_invalid(value: int) -> None:
    """0、超上限 101、负数 -5 均应失败并返回取值无效错误。"""
    result = validate_max_file_size_setting(value)
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_MAX_FILE_SIZE


# --------------------------------------------------------------------------- #
# validate_email —— 合法示例通过；非法示例失败并带 INVALID_EMAIL_FORMAT（需求 2.5）#
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("email", ["a@b.com", "user.name@example.co.uk", "x@y.z"])
def test_validate_email_valid_examples(email: str) -> None:
    """符合“本地名@域名（含点号）”格式的示例应通过。"""
    result = validate_email(email)
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "email",
    [
        "ab.com",      # 缺少 @
        "@b.com",      # 本地名为空
        "a@",          # 域名为空
        "a@b",         # 域名无点号
        "a@@b.com",    # 双 @
    ],
)
def test_validate_email_invalid_examples(email: str) -> None:
    """非法邮箱示例应失败并返回 INVALID_EMAIL_FORMAT（需求 2.5）。"""
    result = validate_email(email)
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_EMAIL_FORMAT


# --------------------------------------------------------------------------- #
# validate_role —— 合法角色通过；大小写错误 / 空串失败                            #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role", ["Admin", "Teacher", "Student"])
def test_validate_role_valid(role: str) -> None:
    """三种合法角色应通过。"""
    result = validate_role(role)
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.unit
@pytest.mark.parametrize("role", ["admin", ""])
def test_validate_role_invalid(role: str) -> None:
    """大小写不符（admin）与空串均应失败并返回角色无效错误。"""
    result = validate_role(role)
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_ROLE


# --------------------------------------------------------------------------- #
# validate_extension —— 大小写不敏感命中通过；非法扩展名 / 无扩展名失败           #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_validate_extension_case_insensitive_pass() -> None:
    """扩展名匹配不区分大小写：report.PDF 命中 pdf 应通过。"""
    result = validate_extension("report.PDF", ALLOWED_EXTENSIONS)
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.unit
@pytest.mark.parametrize("filename", ["report.exe", "report"])
def test_validate_extension_rejected(filename: str) -> None:
    """不在允许集合内的扩展名（exe）及无扩展名（report）均应失败。"""
    result = validate_extension(filename, ALLOWED_EXTENSIONS)
    assert result.ok is False
    assert result.error_code is ErrorCode.EXTENSION_NOT_ALLOWED


# --------------------------------------------------------------------------- #
# validate_required —— 非空非空白为 True；空 / 纯空白 / None 为 False             #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_validate_required_truthy() -> None:
    """非空且含非空白字符的值为必填通过。"""
    assert validate_required("x") is True


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   ", None])
def test_validate_required_falsy(value) -> None:
    """空串、纯空白、None 均视为必填缺失（False）。"""
    assert validate_required(value) is False
