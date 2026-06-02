"""核心业务校验与计算（纯函数）。

依据 design.md「核心校验（纯函数，validators.py）」章节实现。该模块只包含
**无副作用的纯函数**与常量定义：给定相同输入恒得相同输出，不读写数据库、
文件系统、网络或全局状态。校验类函数统一返回 :class:`ValidationResult`
（由服务层据此映射为 HTTP 错误码），布尔判定类函数返回 ``bool``。

设计意图：将业务校验集中于此，使其成为属性测试（Hypothesis）的主要对象
（参见 design.md「Correctness Properties」Property 1、2、6、7、13、23、24、
25、26、27、28）。

语义决策（在对应函数 docstring 中亦有说明）：

* :func:`validate_file_size` 对 ``size <= 0`` 返回 ``EMPTY_FILE``、对超限返回
  ``FILE_TOO_LARGE``。服务层（任务 13.1）会在调用前/后据此区分“文件为空”与
  “文件超过大小限制”两类错误。
* :func:`validate_allowed_extension_set` 对“含越界扩展名”的非子集情形返回
  ``EXTENSION_NOT_ALLOWED``（design 错误码表中与扩展名取值相关的既有错误码），
  对空集合返回 ``NO_EXTENSION_SELECTED``（对应需求 8.9）。
* :func:`validate_extension` 使用 :func:`os.path.splitext` 提取扩展名，因此
  无扩展名（如 ``"report"``）或仅以点号开头的隐藏文件（如 ``".pdf"``）均视为
  “无扩展名”从而被拒绝。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from app.core.errors import ErrorCode
from app.core.results import ValidationResult

__all__ = [
    "ALLOWED_EXTENSIONS",
    "MIN_FILE_SIZE_MB",
    "MAX_FILE_SIZE_MB",
    "DEFAULT_FILE_SIZE_MB",
    "DEFAULT_PASSWORD",
    "SESSION_TTL_MINUTES",
    "VALID_ROLES",
    "validate_email",
    "validate_role",
    "validate_required",
    "validate_length",
    "validate_extension",
    "validate_file_size",
    "validate_max_file_size_setting",
    "normalize_max_file_size",
    "validate_deadline",
    "validate_allowed_extension_set",
    "compute_token_expiry",
    "is_token_valid",
]


# --------------------------------------------------------------------------- #
# 常量定义                                                                      #
# --------------------------------------------------------------------------- #

#: 系统允许的文件扩展名全集（小写、不含点号）。来源：需求 8.8。
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"md", "pdf", "docx", "zip", "rar", "7z"})

#: 作业最大文件大小允许的下限（MB，含）。来源：需求 8.11。
MIN_FILE_SIZE_MB: int = 1

#: 作业最大文件大小允许的上限（MB，含）。来源：需求 8.11。
MAX_FILE_SIZE_MB: int = 100

#: 未指定最大文件大小时的默认值（MB）。来源：需求 8.10。
DEFAULT_FILE_SIZE_MB: int = 5

#: 创建学生时的默认密码。来源：需求 6.3 / 术语表。
DEFAULT_PASSWORD: str = "minglog666"

#: 会话令牌有效期（分钟）。来源：需求 1.1。
SESSION_TTL_MINUTES: int = 30

#: 合法用户角色集合（小写，与前端 Role 类型一致）。
VALID_ROLES: frozenset[str] = frozenset({"admin", "teacher", "student"})


# --------------------------------------------------------------------------- #
# 校验纯函数                                                                    #
# --------------------------------------------------------------------------- #


def validate_email(email: str) -> ValidationResult:
    """校验邮箱是否符合“本地名@域名”格式。

    通过条件（需求 2.5）需同时满足：

    * 恰好包含一个 ``@`` 符号；
    * ``@`` 前的本地名非空；
    * ``@`` 后的域名部分非空且至少包含一个点号（``.``）。

    Returns:
        通过返回 :meth:`ValidationResult.ok_result`；否则返回携带
        :attr:`ErrorCode.INVALID_EMAIL_FORMAT` 的失败结果。
    """
    if not isinstance(email, str) or email.count("@") != 1:
        return ValidationResult.fail(ErrorCode.INVALID_EMAIL_FORMAT)

    local_part, _, domain_part = email.partition("@")
    if local_part == "" or domain_part == "" or "." not in domain_part:
        return ValidationResult.fail(ErrorCode.INVALID_EMAIL_FORMAT)

    return ValidationResult.ok_result()


def validate_role(role: str) -> ValidationResult:
    """校验角色取值是否属于 ``{Admin, Teacher, Student}``（需求 2.2 / 2.7）。

    Returns:
        通过返回成功结果；否则返回携带 :attr:`ErrorCode.INVALID_ROLE` 的失败结果。
    """
    if isinstance(role, str) and role in VALID_ROLES:
        return ValidationResult.ok_result()
    return ValidationResult.fail(ErrorCode.INVALID_ROLE)


def validate_required(value: Optional[str]) -> bool:
    """判断必填字段是否有值：非 ``None``、非空字符串且非纯空白。

    用于统一的“必填字段缺失”校验（需求 1.6、2.6、4.4、5.7、6.9、7.6、8.5）。
    """
    return value is not None and value.strip() != ""


def validate_length(value: str, max_len: int) -> bool:
    """判断字符长度是否未超过上限：``len(value) <= max_len``。

    用于字段长度上限校验（需求 5.4、5.5、5.6、7.4、8.6、8.7）。``None`` 视作
    空字符串（长度 0），其“缺失”语义应由 :func:`validate_required` 单独覆盖。
    """
    text = value if value is not None else ""
    return len(text) <= max_len


def validate_extension(filename: str, allowed: frozenset[str]) -> ValidationResult:
    """校验文件扩展名（不区分大小写）是否属于允许集合（需求 9.4）。

    使用 :func:`os.path.splitext` 提取扩展名：无扩展名（如 ``"report"``）或仅以
    点号开头的隐藏文件（如 ``".pdf"``）均视为“无扩展名”，从而判为不被允许。
    扩展名在比较前会去除前导点号并转为小写。

    Returns:
        通过返回成功结果；否则返回携带 :attr:`ErrorCode.EXTENSION_NOT_ALLOWED`
        的失败结果。
    """
    if not isinstance(filename, str):
        return ValidationResult.fail(ErrorCode.EXTENSION_NOT_ALLOWED)

    _, ext = os.path.splitext(filename)
    normalized = ext[1:].lower() if ext.startswith(".") else ext.lower()
    if normalized != "" and normalized in {e.lower() for e in allowed}:
        return ValidationResult.ok_result()
    return ValidationResult.fail(ErrorCode.EXTENSION_NOT_ALLOWED)


def validate_file_size(size_bytes: int, max_mb: int) -> ValidationResult:
    """校验文件字节大小是否落在 ``0 < size_bytes <= max_mb * 1024 * 1024``。

    语义（需求 9.3 / 9.5）：

    * ``size_bytes <= 0``（缺失或 0 字节）-> :attr:`ErrorCode.EMPTY_FILE`；
    * 超过 ``max_mb`` 对应的字节上限 -> :attr:`ErrorCode.FILE_TOO_LARGE`；
    * 其余（``0 < size_bytes <= 上限``）-> 通过。

    服务层（任务 13.1）据返回的错误码区分“文件为空”与“文件超过大小限制”。
    """
    if size_bytes <= 0:
        return ValidationResult.fail(ErrorCode.EMPTY_FILE)

    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return ValidationResult.fail(ErrorCode.FILE_TOO_LARGE)

    return ValidationResult.ok_result()


def validate_max_file_size_setting(max_mb: Optional[float]) -> ValidationResult:
    """校验作业“最大文件大小”设置取值（需求 8.11）。

    * ``None`` -> 视为合法（创建时将归一化为默认 5MB，见 :func:`normalize_max_file_size`）；
    * 否则必须是位于 ``1..100``（含端点）之间且取整数值的正数；
      非数值、布尔、含小数、越界或非有限值（NaN/Inf）均判为非法。

    Returns:
        通过返回成功结果；否则返回携带 :attr:`ErrorCode.INVALID_MAX_FILE_SIZE`
        的失败结果。
    """
    if max_mb is None:
        return ValidationResult.ok_result()

    # bool 是 int 的子类，需显式排除，避免 True/False 被当作 1/0。
    if isinstance(max_mb, bool) or not isinstance(max_mb, (int, float)):
        return ValidationResult.fail(ErrorCode.INVALID_MAX_FILE_SIZE)

    # 必须为整数值（float 形态也需无小数部分），且为有限值。
    if isinstance(max_mb, float) and not max_mb.is_integer():
        return ValidationResult.fail(ErrorCode.INVALID_MAX_FILE_SIZE)

    value = int(max_mb)
    if MIN_FILE_SIZE_MB <= value <= MAX_FILE_SIZE_MB:
        return ValidationResult.ok_result()
    return ValidationResult.fail(ErrorCode.INVALID_MAX_FILE_SIZE)


def normalize_max_file_size(max_mb: Optional[float]) -> int:
    """归一化最大文件大小：``None`` -> :data:`DEFAULT_FILE_SIZE_MB`，否则取原值。

    返回整数（MB）。应在 :func:`validate_max_file_size_setting` 通过后调用，
    此时非 ``None`` 取值保证为整数值的正数（需求 8.10）。
    """
    if max_mb is None:
        return DEFAULT_FILE_SIZE_MB
    return int(max_mb)


def validate_deadline(deadline: datetime, now: datetime) -> ValidationResult:
    """校验作业截止时间必须晚于当前时间（需求 8.13）。

    Returns:
        ``deadline > now`` 返回成功结果；否则返回携带
        :attr:`ErrorCode.INVALID_DEADLINE` 的失败结果。
    """
    if deadline > now:
        return ValidationResult.ok_result()
    return ValidationResult.fail(ErrorCode.INVALID_DEADLINE)


def validate_allowed_extension_set(exts: frozenset[str]) -> ValidationResult:
    """校验作业“允许扩展名集合”（需求 8.8 / 8.9，对应 Property 23）。

    * 空集合 -> :attr:`ErrorCode.NO_EXTENSION_SELECTED`（至少选择一种扩展名）；
    * 非 :data:`ALLOWED_EXTENSIONS` 的子集（含越界值）->
      :attr:`ErrorCode.EXTENSION_NOT_ALLOWED`（取值无效，复用扩展名相关既有错误码）；
    * 非空且为子集 -> 通过。
    """
    if not exts:
        return ValidationResult.fail(ErrorCode.NO_EXTENSION_SELECTED)
    if not (set(exts) <= ALLOWED_EXTENSIONS):
        return ValidationResult.fail(ErrorCode.EXTENSION_NOT_ALLOWED)
    return ValidationResult.ok_result()


# --------------------------------------------------------------------------- #
# 会话令牌相关计算（纯函数）                                                    #
# --------------------------------------------------------------------------- #


def compute_token_expiry(issued_at: datetime) -> datetime:
    """计算会话令牌过期时间：签发时间 + :data:`SESSION_TTL_MINUTES` 分钟（需求 1.1）。"""
    return issued_at + timedelta(minutes=SESSION_TTL_MINUTES)


def is_token_valid(expiry: datetime, now: datetime) -> bool:
    """判断令牌在 ``now`` 时刻是否仍有效：当且仅当 ``now < expiry``（需求 1.4）。"""
    return now < expiry
