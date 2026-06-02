"""校验结果类型。

依据 design.md「核心校验（纯函数，validators.py）」中的定义，校验纯函数
统一返回 :class:`ValidationResult`，服务层据此映射为 HTTP 错误码。

为减少调用方样板代码，提供两个便捷构造器：

* :meth:`ValidationResult.ok` —— 表示校验通过；
* :meth:`ValidationResult.fail` —— 表示校验失败，并携带具体 :class:`ErrorCode`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.errors import ErrorCode

__all__ = ["ValidationResult"]


@dataclass(frozen=True)
class ValidationResult:
    """不可变的校验结果。

    Attributes:
        ok: 校验是否通过。
        error_code: 当 ``ok=False`` 时为对应的错误码；``ok=True`` 时应为 ``None``。
    """

    ok: bool
    error_code: Optional[ErrorCode] = None  # ok=False 时非空

    def __post_init__(self) -> None:
        # 保持结果自洽：成功不应携带错误码，失败必须携带错误码。
        if self.ok and self.error_code is not None:
            raise ValueError("成功的 ValidationResult 不应携带 error_code")
        if not self.ok and self.error_code is None:
            raise ValueError("失败的 ValidationResult 必须携带 error_code")

    @classmethod
    def ok_result(cls) -> "ValidationResult":
        """构造一个表示校验通过的结果。"""
        return cls(ok=True, error_code=None)

    # 与设计文档保持一致的简短别名：``ValidationResult.ok()`` 语义直观。
    # 注意：实例属性 ``ok`` 与该类方法名冲突，故成功构造器使用 ``ok_result``。

    @classmethod
    def fail(cls, error_code: ErrorCode) -> "ValidationResult":
        """构造一个表示校验失败的结果。

        Args:
            error_code: 失败对应的错误码，不可为 ``None``。
        """
        if error_code is None:  # 防御性校验：避免构造出不自洽的失败结果。
            raise ValueError("fail 必须提供 error_code")
        return cls(ok=False, error_code=error_code)
