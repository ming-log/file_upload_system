"""错误码到 HTTP 映射的单元测试（任务 16.2）。

验证 :mod:`app.api.errors` 中 :data:`ERROR_CODE_TO_HTTP_STATUS` 与
:func:`http_exception_for` 的行为：

* 映射覆盖 :class:`~app.core.errors.ErrorCode` 全部成员（无遗漏）；
* 各错误码映射的状态码与 design.md「错误码与 HTTP 映射」表一致；
* :func:`http_exception_for` 构造的 :class:`HTTPException` 携带正确状态码与
  统一错误体（``error_code`` / ``message`` / ``details``）。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.errors import (
    DEFAULT_ERROR_MESSAGES,
    ERROR_CODE_TO_HTTP_STATUS,
    error_body,
    http_exception_for,
    http_status_for,
)
from app.core.errors import ErrorCode

# design.md「错误码与 HTTP 映射」表的期望值（逐条对照）。
EXPECTED = {
    ErrorCode.MISSING_REQUIRED_FIELD: 400,
    ErrorCode.INVALID_CREDENTIALS: 401,
    ErrorCode.PASSWORD_RESET_REQUIRED: 401,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.INVALID_EMAIL_FORMAT: 400,
    ErrorCode.INVALID_ROLE: 400,
    ErrorCode.DUPLICATE_ACCOUNT: 409,
    ErrorCode.DUPLICATE_STUDENT_ID: 409,
    ErrorCode.EMPTY_BATCH: 400,
    ErrorCode.BATCH_LIMIT_EXCEEDED: 400,
    ErrorCode.FIELD_TOO_LONG: 400,
    ErrorCode.CLASS_NOT_FOUND: 404,
    ErrorCode.COURSE_NOT_FOUND: 404,
    ErrorCode.ASSIGNMENT_NOT_FOUND: 404,
    ErrorCode.NO_EXTENSION_SELECTED: 400,
    ErrorCode.INVALID_MAX_FILE_SIZE: 400,
    ErrorCode.INVALID_DEADLINE: 400,
    ErrorCode.EMPTY_FILE: 400,
    ErrorCode.EXTENSION_NOT_ALLOWED: 400,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.DEADLINE_PASSED: 422,
    ErrorCode.STORAGE_TIMEOUT: 504,
    ErrorCode.STORAGE_FAILED: 502,
}


@pytest.mark.unit
def test_mapping_covers_all_error_codes() -> None:
    """映射与默认消息均覆盖全部 ErrorCode 成员（无遗漏）。"""
    assert set(ERROR_CODE_TO_HTTP_STATUS) == set(ErrorCode)
    assert set(DEFAULT_ERROR_MESSAGES) == set(ErrorCode)


@pytest.mark.unit
@pytest.mark.parametrize("code,status_code", list(EXPECTED.items()))
def test_status_matches_design_table(code: ErrorCode, status_code: int) -> None:
    """每个错误码映射的 HTTP 状态码与 design 表一致。"""
    assert http_status_for(code) == status_code
    assert ERROR_CODE_TO_HTTP_STATUS[code] == status_code


@pytest.mark.unit
def test_error_body_shape() -> None:
    """统一错误体含 error_code / message / details 三字段。"""
    body = error_body(ErrorCode.FORBIDDEN)
    assert body["error_code"] == "FORBIDDEN"
    assert body["message"] == DEFAULT_ERROR_MESSAGES[ErrorCode.FORBIDDEN]
    assert body["details"] == {}


@pytest.mark.unit
def test_error_body_accepts_overrides() -> None:
    """可覆盖 message 与 details。"""
    body = error_body(
        ErrorCode.FIELD_TOO_LONG, message="自定义", details={"field": "school"}
    )
    assert body["message"] == "自定义"
    assert body["details"] == {"field": "school"}


@pytest.mark.unit
def test_http_exception_for_builds_exception() -> None:
    """http_exception_for 构造携带正确状态码与统一错误体的 HTTPException。"""
    exc = http_exception_for(ErrorCode.COURSE_NOT_FOUND)
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 404
    assert exc.detail["error_code"] == "COURSE_NOT_FOUND"
    assert "message" in exc.detail
    assert exc.detail["details"] == {}
