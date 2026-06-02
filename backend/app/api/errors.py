"""``ErrorCode`` → HTTP 状态码的统一映射与错误响应辅助（任务 16.2）。

依据 design.md「Error Handling / 错误码与 HTTP 映射」表，集中定义业务错误码到
HTTP 状态码的映射，并提供构造统一错误响应体与 :class:`fastapi.HTTPException`
的便捷函数，供各业务路由在服务层返回失败结果时复用。

统一错误响应体形态（design.md「统一错误模型」）::

    {"error_code": "EXTENSION_NOT_ALLOWED", "message": "文件扩展名不被允许", "details": {}}

该响应体作为 :class:`fastapi.HTTPException` 的 ``detail`` 传出，因此最终 JSON
形如 ``{"detail": {"error_code": ..., "message": ..., "details": {}}}``——与
:mod:`app.api.deps` 中 401/403 的既有约定保持一致（``resp.json()["detail"]
["error_code"]``）。

设计取舍：
* **全覆盖**：:data:`ERROR_CODE_TO_HTTP_STATUS` 覆盖 :class:`~app.core.errors.ErrorCode`
  的**全部**成员；模块导入时通过断言校验「无遗漏」，避免新增错误码后忘记映射。
* **默认消息**：:data:`DEFAULT_ERROR_MESSAGES` 为每个错误码提供中文默认说明
  （取自 design 错误码表「含义」列）。调用方可传入更具体的 ``message`` 覆盖。
* **可追溯**：每条映射的 HTTP 状态码与 design 表一一对应（见行内注释）。
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, status

from app.core.errors import ErrorCode

__all__ = [
    "ERROR_CODE_TO_HTTP_STATUS",
    "DEFAULT_ERROR_MESSAGES",
    "http_status_for",
    "error_body",
    "http_exception_for",
]


# --------------------------------------------------------------------------- #
# 错误码 → HTTP 状态码映射（design.md「错误码与 HTTP 映射」表全量）              #
# --------------------------------------------------------------------------- #

ERROR_CODE_TO_HTTP_STATUS: dict[ErrorCode, int] = {
    # 必填字段缺失 | 400 | 需求 1.6, 2.6, 4.4, 5.7, 6.9, 7.6, 8.5
    ErrorCode.MISSING_REQUIRED_FIELD: status.HTTP_400_BAD_REQUEST,
    # 账号或密码错误 | 401 | 需求 1.2
    ErrorCode.INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
    # 需要重置密码 | 401 | 需求 1.5
    ErrorCode.PASSWORD_RESET_REQUIRED: status.HTTP_401_UNAUTHORIZED,
    # 未认证（令牌缺失/无效/过期） | 401 | 需求 1.4
    ErrorCode.UNAUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
    # 权限不足 | 403 | 需求 4.2, 5.2, 6.8, 8.2, 9.2
    ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    # 邮箱格式错误 | 400 | 需求 2.5
    ErrorCode.INVALID_EMAIL_FORMAT: status.HTTP_400_BAD_REQUEST,
    # 角色取值无效 | 400 | 需求 2.7
    ErrorCode.INVALID_ROLE: status.HTTP_400_BAD_REQUEST,
    # 账号重复 | 409 | 需求 2.3
    ErrorCode.DUPLICATE_ACCOUNT: status.HTTP_409_CONFLICT,
    # 学号重复 | 409 | 需求 6.7
    ErrorCode.DUPLICATE_STUDENT_ID: status.HTTP_409_CONFLICT,
    # 批量记录为空 | 400 | 需求 3.4
    ErrorCode.EMPTY_BATCH: status.HTTP_400_BAD_REQUEST,
    # 批量记录数超过上限 | 400 | 需求 3.5
    ErrorCode.BATCH_LIMIT_EXCEEDED: status.HTTP_400_BAD_REQUEST,
    # 字段超长（含字段名） | 400 | 需求 5.4-5.6, 7.4, 8.6, 8.7
    ErrorCode.FIELD_TOO_LONG: status.HTTP_400_BAD_REQUEST,
    # 班级不存在 | 404 | 需求 7.5
    ErrorCode.CLASS_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    # 课程不存在 | 404 | 需求 8.12
    ErrorCode.COURSE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    # 作业不存在 | 404 | 需求 9.1
    ErrorCode.ASSIGNMENT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    # 未选择任何允许扩展名 | 400 | 需求 8.9
    ErrorCode.NO_EXTENSION_SELECTED: status.HTTP_400_BAD_REQUEST,
    # 最大文件大小取值无效 | 400 | 需求 8.11
    ErrorCode.INVALID_MAX_FILE_SIZE: status.HTTP_400_BAD_REQUEST,
    # 截止时间无效 | 400 | 需求 8.13
    ErrorCode.INVALID_DEADLINE: status.HTTP_400_BAD_REQUEST,
    # 文件为空 | 400 | 需求 9.3
    ErrorCode.EMPTY_FILE: status.HTTP_400_BAD_REQUEST,
    # 扩展名不被允许 | 400 | 需求 9.4
    ErrorCode.EXTENSION_NOT_ALLOWED: status.HTTP_400_BAD_REQUEST,
    # 文件超过大小限制 | 413 | 需求 9.5
    # 使用字面量 413，避免不同 starlette 版本对该常量命名的弃用差异。
    ErrorCode.FILE_TOO_LARGE: 413,
    # 已超过截止时间 | 422 | 需求 9.6
    # 使用字面量 422，避免不同 starlette 版本对该常量命名的弃用差异。
    ErrorCode.DEADLINE_PASSED: 422,
    # 存储超时 | 504 | 需求 10.2
    ErrorCode.STORAGE_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    # 文件保存失败 | 502 | 需求 10.3
    ErrorCode.STORAGE_FAILED: status.HTTP_502_BAD_GATEWAY,
}


# --------------------------------------------------------------------------- #
# 默认错误说明（取自 design 错误码表「含义」列）                                 #
# --------------------------------------------------------------------------- #

DEFAULT_ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.MISSING_REQUIRED_FIELD: "必填字段缺失",
    ErrorCode.INVALID_CREDENTIALS: "账号或密码错误",
    ErrorCode.PASSWORD_RESET_REQUIRED: "需要重置密码",
    ErrorCode.UNAUTHENTICATED: "未认证：令牌缺失、无效或已过期",
    ErrorCode.FORBIDDEN: "权限不足",
    ErrorCode.INVALID_EMAIL_FORMAT: "邮箱格式错误",
    ErrorCode.INVALID_ROLE: "角色取值无效",
    ErrorCode.DUPLICATE_ACCOUNT: "账号重复",
    ErrorCode.DUPLICATE_STUDENT_ID: "学号重复",
    ErrorCode.EMPTY_BATCH: "批量记录为空",
    ErrorCode.BATCH_LIMIT_EXCEEDED: "批量记录数超过上限",
    ErrorCode.FIELD_TOO_LONG: "字段超长",
    ErrorCode.CLASS_NOT_FOUND: "班级不存在",
    ErrorCode.COURSE_NOT_FOUND: "课程不存在",
    ErrorCode.ASSIGNMENT_NOT_FOUND: "作业不存在",
    ErrorCode.NO_EXTENSION_SELECTED: "未选择任何允许扩展名",
    ErrorCode.INVALID_MAX_FILE_SIZE: "最大文件大小取值无效",
    ErrorCode.INVALID_DEADLINE: "截止时间无效",
    ErrorCode.EMPTY_FILE: "文件为空",
    ErrorCode.EXTENSION_NOT_ALLOWED: "文件扩展名不被允许",
    ErrorCode.FILE_TOO_LARGE: "文件超过大小限制",
    ErrorCode.DEADLINE_PASSED: "已超过截止时间",
    ErrorCode.STORAGE_TIMEOUT: "存储超时",
    ErrorCode.STORAGE_FAILED: "文件保存失败",
}


# 导入期一致性校验：确保映射与默认消息覆盖全部错误码（无遗漏/无多余）。
# 新增 ErrorCode 成员后若忘记补充映射，将在导入时立即暴露。
_ALL_CODES = set(ErrorCode)
assert set(ERROR_CODE_TO_HTTP_STATUS) == _ALL_CODES, (
    "ERROR_CODE_TO_HTTP_STATUS 必须覆盖全部 ErrorCode 成员："
    f"缺失 {_ALL_CODES - set(ERROR_CODE_TO_HTTP_STATUS)}，"
    f"多余 {set(ERROR_CODE_TO_HTTP_STATUS) - _ALL_CODES}"
)
assert set(DEFAULT_ERROR_MESSAGES) == _ALL_CODES, (
    "DEFAULT_ERROR_MESSAGES 必须覆盖全部 ErrorCode 成员："
    f"缺失 {_ALL_CODES - set(DEFAULT_ERROR_MESSAGES)}"
)


# --------------------------------------------------------------------------- #
# 辅助函数                                                                      #
# --------------------------------------------------------------------------- #


def http_status_for(error_code: ErrorCode) -> int:
    """返回给定业务错误码对应的 HTTP 状态码。

    Args:
        error_code: 业务错误码。

    Returns:
        对应的 HTTP 状态码整数。未知错误码（理论上不会发生，因已做全覆盖断言）
        回退为 ``400 Bad Request``。
    """
    return ERROR_CODE_TO_HTTP_STATUS.get(error_code, status.HTTP_400_BAD_REQUEST)


def error_body(
    error_code: ErrorCode,
    message: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """构造统一错误响应体 ``{error_code, message, details}``。

    Args:
        error_code: 业务错误码（``error_code`` 字段取其 ``value``）。
        message: 可选的人类可读说明；缺省取 :data:`DEFAULT_ERROR_MESSAGES`。
        details: 可选的补充信息字典（如超长字段名）；缺省为空字典。

    Returns:
        统一错误响应体字典。
    """
    return {
        "error_code": error_code.value,
        "message": message
        if message is not None
        else DEFAULT_ERROR_MESSAGES.get(error_code, error_code.value),
        "details": details if details is not None else {},
    }


def http_exception_for(
    error_code: ErrorCode,
    *,
    message: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> HTTPException:
    """据业务错误码构造映射好状态码与统一响应体的 :class:`HTTPException`。

    用法::

        result = service.create_course(...)
        if not result.ok:
            raise http_exception_for(result.error_code)

    Args:
        error_code: 业务错误码，决定 HTTP 状态码与默认消息。
        message: 可选的说明覆盖。
        details: 可选的补充信息字典。

    Returns:
        可直接 ``raise`` 的 :class:`fastapi.HTTPException`。
    """
    return HTTPException(
        status_code=http_status_for(error_code),
        detail=error_body(error_code, message=message, details=details),
    )
