"""认证服务（Auth_Service）。

依据 design.md「Auth_Service」与需求 1（用户认证与登录）实现登录与令牌校验：

* :meth:`AuthService.login` —— 校验账号/密码非空 -> 查找用户 -> 校验存储密码非空
  -> 校验凭据匹配 -> 签发含 ``role`` 与 ``exp`` (= ``now + 30min``) 的 JWT。
* :meth:`AuthService.verify_token` —— 解析令牌；缺失/无效/过期 -> ``UNAUTHENTICATED``；
  有效 -> 返回 ``(role, account)``。

校验与时间计算复用 :mod:`app.core.validators` 中的纯函数（``validate_required``、
``compute_token_expiry``、``is_token_valid``），使过期判定可由调用方注入的 ``now``
确定性驱动、便于属性测试（参见 design.md Property 1–5）。

设计与安全决策
--------------

* **密码存储**：依据 Data Models，``User.password`` 以**明文**存储，故此处采用明文
  相等比较；为降低时序侧信道风险，使用 :func:`hmac.compare_digest` 进行**常量时间**
  比较。本任务范围内不引入哈希（如需哈希需另行调整模型与创建流程）。
* **令牌过期判定**：本服务**不**依赖 python-jose 的自动 ``exp`` 校验（其基于真实
  墙钟时间），而是关闭该校验并改用 :func:`is_token_valid` 对照调用方传入的 ``now``
  判断，从而保证确定性与可测试性。
* **JWT 时间声明编码（供下游中间件 task 16.1 参考）**：
    - ``iat`` / ``exp`` 以**整数 POSIX 时间戳**写入（秒精度）。
    - 编码：``calendar.timegm(dt.utctimetuple())``——naive datetime 视为 UTC，
      aware datetime 转换为 UTC，两者一致。
    - 解码：依据传入 ``now`` 的 tz 属性重建 ``expiry`` datetime（``now`` 为 naive ->
      重建为 naive-UTC；``now`` 为 aware -> 重建为 aware-UTC），再交由
      :func:`is_token_valid` 比较，避免 naive/aware 混用导致的比较异常。
* **密钥可配置**：``SECRET_KEY`` 默认取环境变量 ``AUTH_SECRET_KEY``，缺省提供一个
  仅供开发使用的占位值；生产环境必须通过环境变量注入强随机密钥。
"""

from __future__ import annotations

import calendar
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from jose import JWTError, jwt

from app.core.errors import ErrorCode
from app.core.validators import (
    compute_token_expiry,
    is_token_valid,
    validate_required,
)
from app.repository import Repository

__all__ = [
    "ALGORITHM",
    "SECRET_KEY",
    "AuthService",
    "LoginResult",
    "TokenResult",
]


# --------------------------------------------------------------------------- #
# 模块级配置                                                                    #
# --------------------------------------------------------------------------- #

#: JWT 签名算法（HMAC-SHA256）。
ALGORITHM: str = "HS256"

#: JWT 签名密钥。优先取环境变量 ``AUTH_SECRET_KEY``；缺省值仅供本地开发，
#: 生产环境必须通过环境变量注入强随机密钥。
SECRET_KEY: str = os.environ.get(
    "AUTH_SECRET_KEY", "dev-insecure-secret-change-me"
)


# --------------------------------------------------------------------------- #
# 结果类型                                                                      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LoginResult:
    """登录结果。

    Attributes:
        ok: 是否登录成功。
        error_code: 失败时对应的错误码；成功时为 ``None``。
        token: 成功时签发的 JWT 会话令牌；失败时为 ``None``（不返回令牌）。
        role: 成功时登录用户的角色；失败时为 ``None``。
    """

    ok: bool
    error_code: Optional[ErrorCode] = None
    token: Optional[str] = None
    role: Optional[str] = None

    @classmethod
    def success(cls, token: str, role: str) -> "LoginResult":
        return cls(ok=True, error_code=None, token=token, role=role)

    @classmethod
    def fail(cls, error_code: ErrorCode) -> "LoginResult":
        return cls(ok=False, error_code=error_code, token=None, role=None)


@dataclass(frozen=True)
class TokenResult:
    """令牌校验结果。

    Attributes:
        ok: 令牌是否有效。
        error_code: 无效时对应的错误码（恒为 ``UNAUTHENTICATED``）；有效时为 ``None``。
        role: 有效时令牌携带的角色；无效时为 ``None``。
        account: 有效时令牌主体（``sub``，即账号）；无效时为 ``None``。
    """

    ok: bool
    error_code: Optional[ErrorCode] = None
    role: Optional[str] = None
    account: Optional[str] = None

    @classmethod
    def success(cls, role: str, account: str) -> "TokenResult":
        return cls(ok=True, error_code=None, role=role, account=account)

    @classmethod
    def unauthenticated(cls) -> "TokenResult":
        return cls(ok=False, error_code=ErrorCode.UNAUTHENTICATED, role=None, account=None)


# --------------------------------------------------------------------------- #
# 时间戳编解码辅助（与下游中间件保持一致的约定）                                 #
# --------------------------------------------------------------------------- #


def _to_timestamp(dt: datetime) -> int:
    """将 datetime 转为整数 POSIX 时间戳（秒）。

    naive datetime 视为 UTC，aware datetime 转换为 UTC，二者结果一致。
    """
    return calendar.timegm(dt.utctimetuple())


def _expiry_from_claim(exp_value: int, now: datetime) -> datetime:
    """依据 ``now`` 的 tz 属性，将 ``exp`` 时间戳重建为可与 ``now`` 比较的 datetime。

    * ``now`` 为 naive -> 重建为 naive-UTC（去除 tzinfo）；
    * ``now`` 为 aware -> 重建为 aware-UTC。
    """
    aware = datetime.fromtimestamp(exp_value, tz=timezone.utc)
    if now.tzinfo is None:
        return aware.replace(tzinfo=None)
    return aware


# --------------------------------------------------------------------------- #
# 认证服务                                                                      #
# --------------------------------------------------------------------------- #


class AuthService:
    """登录与会话令牌校验服务。

    Args:
        repository: 用于按账号查找用户的仓储。通过构造注入，便于在测试中替换为
            指向内存 SQLite 的仓储或测试替身。
        secret_key: 可选的 JWT 签名密钥；缺省使用模块级 :data:`SECRET_KEY`。
        algorithm: 可选的签名算法；缺省使用模块级 :data:`ALGORITHM`。
    """

    def __init__(
        self,
        repository: Repository,
        *,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
    ) -> None:
        self._repository = repository
        self._secret_key = secret_key if secret_key is not None else SECRET_KEY
        self._algorithm = algorithm if algorithm is not None else ALGORITHM

    # ------------------------------------------------------------------ #
    # 登录（需求 1.1, 1.2, 1.3, 1.5, 1.6）                                  #
    # ------------------------------------------------------------------ #

    def login(self, account: str, password: str, now: datetime) -> LoginResult:
        """校验凭据并在成功时签发会话令牌。

        处理顺序：

        1. 账号或密码为空（``validate_required``）-> ``MISSING_REQUIRED_FIELD``（需求 1.6）。
        2. 账号不存在 -> ``INVALID_CREDENTIALS``（需求 1.2）。
        3. 存储密码为空 -> ``PASSWORD_RESET_REQUIRED``（需求 1.5）。
        4. 提供的密码与存储密码不匹配 -> ``INVALID_CREDENTIALS``（需求 1.2）。
        5. 通过 -> 签发含 ``sub`` / ``role`` / ``iat`` / ``exp`` 的 JWT 并返回
           令牌与角色（需求 1.1, 1.3）。``exp`` = ``compute_token_expiry(now)``
           （即 ``now + 30min``）。

        失败时一律不返回令牌。
        """
        # 1) 必填字段缺失（账号 / 密码任一为空或纯空白）。
        if not validate_required(account) or not validate_required(password):
            return LoginResult.fail(ErrorCode.MISSING_REQUIRED_FIELD)

        # 2) 用户查找：账号不存在 -> 账号或密码错误。
        user = self._repository.get_user_by_account(account)
        if user is None:
            return LoginResult.fail(ErrorCode.INVALID_CREDENTIALS)

        # 3) 存储密码为空 -> 需要重置密码（空密码用户禁止密码登录）。
        if not user.password:
            return LoginResult.fail(ErrorCode.PASSWORD_RESET_REQUIRED)

        # 4) 凭据匹配：常量时间比较，避免时序侧信道。
        if not hmac.compare_digest(
            password.encode("utf-8"), user.password.encode("utf-8")
        ):
            return LoginResult.fail(ErrorCode.INVALID_CREDENTIALS)

        # 5) 签发令牌：exp = now + 30min（compute_token_expiry）。
        expiry = compute_token_expiry(now)
        claims = {
            "sub": user.account,
            "role": user.role,
            "iat": _to_timestamp(now),
            "exp": _to_timestamp(expiry),
        }
        token = jwt.encode(claims, self._secret_key, algorithm=self._algorithm)
        return LoginResult.success(token=token, role=user.role)

    # ------------------------------------------------------------------ #
    # 令牌校验（需求 1.3, 1.4）                                             #
    # ------------------------------------------------------------------ #

    def verify_token(self, token: Optional[str], now: datetime) -> TokenResult:
        """解析并校验会话令牌。

        * 令牌缺失（``None`` / 空 / 纯空白）、签名无效、结构无法解析 ->
          ``UNAUTHENTICATED``（需求 1.4）。
        * 已过期（``is_token_valid(expiry, now)`` 为假）-> ``UNAUTHENTICATED``（需求 1.4）。
        * 有效 -> 返回 ``(role, account)``（需求 1.3, 1.4）。

        过期判定不依赖 JWT 库的自动 ``exp`` 校验，而是关闭该校验后改用
        :func:`is_token_valid` 对照传入的 ``now`` 判断（确定性、可测试）。
        """
        if not isinstance(token, str) or token.strip() == "":
            return TokenResult.unauthenticated()

        try:
            claims = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                # 关闭库内置的 exp 校验：过期由 is_token_valid + 注入的 now 判定。
                options={"verify_exp": False},
            )
        except JWTError:
            # 签名错误、结构损坏、算法不符等一律视为未认证。
            return TokenResult.unauthenticated()

        role = claims.get("role")
        account = claims.get("sub")
        exp_value = claims.get("exp")

        # 必备声明缺失或类型异常 -> 视为无效令牌。
        if not isinstance(role, str) or not isinstance(account, str):
            return TokenResult.unauthenticated()
        if not isinstance(exp_value, (int, float)) or isinstance(exp_value, bool):
            return TokenResult.unauthenticated()

        expiry = _expiry_from_claim(int(exp_value), now)
        if not is_token_valid(expiry, now):
            return TokenResult.unauthenticated()

        return TokenResult.success(role=role, account=account)
