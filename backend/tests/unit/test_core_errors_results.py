"""统一错误模型与校验结果类型的单元测试。

覆盖 design.md「Error Handling」错误码表的完整性，以及 ValidationResult
便捷构造器与自洽性约束（成功不带错误码、失败必带错误码）。
"""

from __future__ import annotations

import pytest

from app.core.errors import ErrorCode
from app.core.results import ValidationResult

# design.md「错误码与 HTTP 映射」表中的全部错误码（成员名）。
EXPECTED_ERROR_CODES = {
    "MISSING_REQUIRED_FIELD",
    "INVALID_CREDENTIALS",
    "PASSWORD_RESET_REQUIRED",
    "UNAUTHENTICATED",
    "FORBIDDEN",
    "INVALID_EMAIL_FORMAT",
    "INVALID_ROLE",
    "DUPLICATE_ACCOUNT",
    "DUPLICATE_STUDENT_ID",
    "EMPTY_BATCH",
    "BATCH_LIMIT_EXCEEDED",
    "FIELD_TOO_LONG",
    "CLASS_NOT_FOUND",
    "COURSE_NOT_FOUND",
    "ASSIGNMENT_NOT_FOUND",
    "NO_EXTENSION_SELECTED",
    "INVALID_MAX_FILE_SIZE",
    "INVALID_DEADLINE",
    "EMPTY_FILE",
    "EXTENSION_NOT_ALLOWED",
    "FILE_TOO_LARGE",
    "DEADLINE_PASSED",
    "STORAGE_TIMEOUT",
    "STORAGE_FAILED",
}


@pytest.mark.unit
def test_error_code_covers_design_table_exactly() -> None:
    """ErrorCode 枚举与设计错误码表完全一致（不缺失、不多余）。"""
    actual = {member.name for member in ErrorCode}
    assert actual == EXPECTED_ERROR_CODES


@pytest.mark.unit
def test_error_code_value_matches_name() -> None:
    """每个错误码的字符串值与成员名一致，便于 JSON 序列化与日志。"""
    for member in ErrorCode:
        assert member.value == member.name
    # str(ErrorCode) 直接产出可读的错误码字符串。
    assert str(ErrorCode.EXTENSION_NOT_ALLOWED) == "EXTENSION_NOT_ALLOWED"


@pytest.mark.unit
def test_error_code_is_str_enum() -> None:
    """ErrorCode 继承自 str，可直接用于字符串比较与序列化。"""
    assert isinstance(ErrorCode.EMPTY_FILE, str)
    assert ErrorCode.EMPTY_FILE == "EMPTY_FILE"


@pytest.mark.unit
def test_validation_result_ok_constructor() -> None:
    """ok_result() 表示通过：ok 为 True 且无错误码。"""
    result = ValidationResult.ok_result()
    assert result.ok is True
    assert result.error_code is None


@pytest.mark.unit
def test_validation_result_fail_constructor() -> None:
    """fail() 表示失败：ok 为 False 且携带给定错误码。"""
    result = ValidationResult.fail(ErrorCode.INVALID_EMAIL_FORMAT)
    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_EMAIL_FORMAT


@pytest.mark.unit
def test_validation_result_is_frozen() -> None:
    """ValidationResult 为不可变（frozen）数据类。"""
    result = ValidationResult.ok_result()
    with pytest.raises(Exception):
        result.ok = False  # type: ignore[misc]


@pytest.mark.unit
def test_validation_result_rejects_inconsistent_states() -> None:
    """成功不可带错误码；失败必须带错误码。"""
    with pytest.raises(ValueError):
        ValidationResult(ok=True, error_code=ErrorCode.EMPTY_FILE)
    with pytest.raises(ValueError):
        ValidationResult(ok=False, error_code=None)
