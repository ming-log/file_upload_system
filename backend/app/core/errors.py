"""统一业务错误模型。

依据 design.md「Error Handling」章节定义的错误码表，集中声明全部业务
错误码。错误统一以 :class:`ErrorCode` 枚举表达：由服务层抛出/返回，API
层据此映射为 HTTP 状态码与统一响应体，例如::

    {"error_code": "EXTENSION_NOT_ALLOWED", "message": "...", "details": {}}

为便于 JSON 序列化与日志记录，:class:`ErrorCode` 继承自 ``str``，其值与
成员名一致（即 ``ErrorCode.EXTENSION_NOT_ALLOWED.value == "EXTENSION_NOT_ALLOWED"``）。
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ErrorCode"]


class ErrorCode(str, Enum):
    """业务错误码枚举（覆盖 design.md 错误码与 HTTP 映射表全部条目）。

    每个成员的注释标注其设计含义、对应 HTTP 状态码与来源需求条款，
    便于在 API 层实现 ``ErrorCode`` → HTTP 的统一映射时进行追溯。
    """

    # 必填字段缺失 | HTTP 400 | 需求 1.6, 2.6, 4.4, 5.7, 6.9, 7.6, 8.5
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    # 账号或密码错误 | HTTP 401 | 需求 1.2
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    # 需要重置密码 | HTTP 401 | 需求 1.5
    PASSWORD_RESET_REQUIRED = "PASSWORD_RESET_REQUIRED"
    # 未认证（令牌缺失/无效/过期） | HTTP 401 | 需求 1.4
    UNAUTHENTICATED = "UNAUTHENTICATED"
    # 权限不足 | HTTP 403 | 需求 4.2, 5.2, 6.8, 8.2, 9.2
    FORBIDDEN = "FORBIDDEN"
    # 邮箱格式错误 | HTTP 400 | 需求 2.5
    INVALID_EMAIL_FORMAT = "INVALID_EMAIL_FORMAT"
    # 角色取值无效 | HTTP 400 | 需求 2.7
    INVALID_ROLE = "INVALID_ROLE"
    # 账号重复 | HTTP 409 | 需求 2.3
    DUPLICATE_ACCOUNT = "DUPLICATE_ACCOUNT"
    # 学号重复 | HTTP 409 | 需求 6.7
    DUPLICATE_STUDENT_ID = "DUPLICATE_STUDENT_ID"
    # 批量记录为空 | HTTP 400 | 需求 3.4
    EMPTY_BATCH = "EMPTY_BATCH"
    # 批量记录数超过上限 | HTTP 400 | 需求 3.5
    BATCH_LIMIT_EXCEEDED = "BATCH_LIMIT_EXCEEDED"
    # 字段超长（含字段名） | HTTP 400 | 需求 5.4-5.6, 7.4, 8.6, 8.7
    FIELD_TOO_LONG = "FIELD_TOO_LONG"
    # 班级不存在 | HTTP 404 | 需求 7.5
    CLASS_NOT_FOUND = "CLASS_NOT_FOUND"
    # 课程不存在 | HTTP 404 | 需求 8.12
    COURSE_NOT_FOUND = "COURSE_NOT_FOUND"
    # 作业不存在 | HTTP 404 | 需求 9.1
    ASSIGNMENT_NOT_FOUND = "ASSIGNMENT_NOT_FOUND"
    # 未选择任何允许扩展名 | HTTP 400 | 需求 8.9
    NO_EXTENSION_SELECTED = "NO_EXTENSION_SELECTED"
    # 最大文件大小取值无效 | HTTP 400 | 需求 8.11
    INVALID_MAX_FILE_SIZE = "INVALID_MAX_FILE_SIZE"
    # 截止时间无效 | HTTP 400 | 需求 8.13
    INVALID_DEADLINE = "INVALID_DEADLINE"
    # 文件为空 | HTTP 400 | 需求 9.3
    EMPTY_FILE = "EMPTY_FILE"
    # 扩展名不被允许 | HTTP 400 | 需求 9.4
    EXTENSION_NOT_ALLOWED = "EXTENSION_NOT_ALLOWED"
    # 文件超过大小限制 | HTTP 413 | 需求 9.5
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    # 已超过截止时间 | HTTP 422 | 需求 9.6
    DEADLINE_PASSED = "DEADLINE_PASSED"
    # 存储超时 | HTTP 504 | 需求 10.2
    STORAGE_TIMEOUT = "STORAGE_TIMEOUT"
    # 文件保存失败 | HTTP 502 | 需求 10.3
    STORAGE_FAILED = "STORAGE_FAILED"

    def __str__(self) -> str:  # pragma: no cover - 便于日志/调试输出
        return self.value
