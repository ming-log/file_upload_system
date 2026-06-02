"""认证中间件辅助（与 :mod:`app.api.deps` 协同）。

依据 design.md「请求认证流程」与「分层职责 / 认证中间件」实现请求认证所需的
**令牌提取**能力，并提供一个可选的、非强制的 Starlette 中间件用于在
``request.state`` 上挂载已解析的 Bearer 令牌，便于日志/诊断与下游复用。

职责划分（保持与 :mod:`app.api.deps` 的一致性）：

* 本模块只负责从 ``Authorization`` 请求头中**解析** Bearer 令牌
  （:func:`parse_bearer_token`），不触达数据库、不做签名校验。
* 令牌的**签名/过期校验**与 ``current_user`` 的**注入**由
  :mod:`app.api.deps` 的 :func:`~app.api.deps.get_current_user` 依赖完成；
  对受保护资源而言，令牌**缺失/无效/过期**会在该依赖中触发 ``401
  UNAUTHENTICATED``（需求 1.4），二者共用同一套 Bearer 解析逻辑。

关于强制鉴权的位置（重要设计决策）
--------------------------------

认证强制（即「无有效令牌 -> 401」）刻意放在**路由级依赖**
（:func:`~app.api.deps.get_current_user` / :func:`~app.api.deps.require_roles`）
而非全局中间件中。原因：公共端点（``/health``、登录接口等）不应被全局拦截；
由路由按需声明 ``Depends(get_current_user)`` 来标记「受保护资源」，可精确地对
受保护资源返回 401，而对公共端点放行——这与 design.md 时序图「请求受保护资源」
的语义一致。

:class:`BearerTokenContextMiddleware` 仅做**上下文挂载**（解析并存入
``request.state.bearer_token``），永不主动拒绝请求，因此可安全地全局启用而不会
影响公共端点。
"""

from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

__all__ = [
    "AUTHORIZATION_HEADER",
    "BEARER_SCHEME",
    "parse_bearer_token",
    "BearerTokenContextMiddleware",
]

#: 承载令牌的标准请求头名称。
AUTHORIZATION_HEADER = "Authorization"

#: Bearer 认证方案名（比较时不区分大小写）。
BEARER_SCHEME = "bearer"


def parse_bearer_token(header: Optional[str]) -> Optional[str]:
    """从 ``Authorization`` 请求头值中解析出 Bearer 令牌。

    解析规则（宽松但安全）：

    * 头部缺失（``None``）或类型异常 -> 返回 ``None``；
    * 必须形如 ``"Bearer <token>"``：方案名不区分大小写（``bearer`` / ``Bearer``
      / ``BEARER`` 均可），方案与令牌之间以一个或多个空白分隔；
    * 缺少令牌部分（仅 ``"Bearer"``）或令牌为空白 -> 返回 ``None``；
    * 方案名不是 ``Bearer`` -> 返回 ``None``。

    返回 ``None`` 表示「无法获得有效的 Bearer 令牌」，调用方
    （:func:`app.api.deps.get_current_user`）会将其交给
    :meth:`AuthService.verify_token`，后者对 ``None`` 一律判为
    ``UNAUTHENTICATED``（需求 1.4）。

    Args:
        header: ``Authorization`` 请求头的原始字符串值，可能为 ``None``。

    Returns:
        解析出的令牌字符串；无法解析时返回 ``None``。
    """
    if not isinstance(header, str):
        return None

    # 按首个空白分割为「方案 + 令牌」两段；split(None, 1) 会折叠多余空白。
    parts = header.strip().split(None, 1)
    if len(parts) != 2:
        return None

    scheme, token = parts
    if scheme.lower() != BEARER_SCHEME:
        return None

    token = token.strip()
    if token == "":
        return None
    return token


class BearerTokenContextMiddleware(BaseHTTPMiddleware):
    """可选的非强制中间件：将已解析的 Bearer 令牌挂载到 ``request.state``。

    该中间件**不**执行签名/过期校验，也**不**拒绝任何请求，仅把
    :func:`parse_bearer_token` 的结果写入 ``request.state.bearer_token``
    （无令牌时为 ``None``），供日志、审计或下游依赖按需读取。强制鉴权仍由
    路由级依赖 :func:`app.api.deps.get_current_user` 负责（对受保护资源返回 401）。

    之所以采用「仅挂载、不拦截」的策略，是为了让公共端点（如 ``/health``、登录
    接口）在全局启用本中间件时仍可正常放行，避免误伤（见模块级说明）。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request.state.bearer_token = parse_bearer_token(
            request.headers.get(AUTHORIZATION_HEADER)
        )
        return await call_next(request)
