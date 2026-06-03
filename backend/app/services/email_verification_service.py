"""邮箱验证码服务（Email_Verification_Service）。

为「学生首次登录强制邮箱验证 + 改密」提供验证码的生成、存储与校验：

* :meth:`generate` —— 为某用户生成 6 位数字验证码，存入进程内存（以 ``user_id``
  为键），返回明文验证码（由调用方发送到用户邮箱）。
* :meth:`verify` —— 校验用户提交的验证码是否正确且未过期。成功后即移除（一次性）。

与 :mod:`app.services.captcha_service` 类似采用进程内存存储，适合单进程部署；多实例
部署应替换为共享存储（如 Redis）。验证码默认 6 位、10 分钟过期、最多尝试 5 次。
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

__all__ = ["EMAIL_CODE_TTL_SECONDS", "EMAIL_CODE_LENGTH", "EmailVerificationService"]

#: 邮箱验证码有效期（秒）。
EMAIL_CODE_TTL_SECONDS: int = 600

#: 验证码位数。
EMAIL_CODE_LENGTH: int = 6

#: 单个验证码允许的最大校验尝试次数（超过即失效，防暴力穷举）。
MAX_ATTEMPTS: int = 5


@dataclass
class _Code:
    code: str
    expires_at: float
    attempts: int = field(default=0)


def _random_code(length: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


class EmailVerificationService:
    """邮箱验证码生成与校验服务（进程内存存储，一次性使用）。"""

    def __init__(
        self,
        *,
        ttl_seconds: int = EMAIL_CODE_TTL_SECONDS,
        length: int = EMAIL_CODE_LENGTH,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.length = length
        self._store: Dict[str, _Code] = {}

    def _now(self) -> float:
        return time.time()

    def generate(self, key: str, now: Optional[float] = None) -> str:
        """为 ``key``（通常为 user_id）生成并存储验证码，返回明文验证码。"""
        current = self._now() if now is None else now
        code = _random_code(self.length)
        self._store[key] = _Code(code=code, expires_at=current + self.ttl_seconds)
        return code

    def verify(self, key: str, code: Optional[str], now: Optional[float] = None) -> bool:
        """校验 ``key`` 对应验证码；成功或超限/过期后移除。"""
        if not code:
            return False
        current = self._now() if now is None else now
        entry = self._store.get(key)
        if entry is None:
            return False
        if entry.expires_at <= current:
            self._store.pop(key, None)
            return False
        entry.attempts += 1
        if entry.attempts > MAX_ATTEMPTS:
            self._store.pop(key, None)
            return False
        if secrets.compare_digest(entry.code, code.strip()):
            self._store.pop(key, None)
            return True
        return False
