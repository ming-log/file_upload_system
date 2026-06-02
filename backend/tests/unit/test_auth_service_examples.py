"""AuthService 的示例 / 边界单元测试（任务 5.5）。

与属性测试（tests/properties/，任务 5.2–5.4）互补：本文件以**具体示例与边界值**
覆盖 ``app.services.auth_service.AuthService`` 的登录与令牌校验关键路径。

来源依据（需求 1）：
- 1.1 凭据通过 -> 返回含角色的会话令牌，有效期自签发起 30 分钟；
- 1.2 账号不存在 / 密码不匹配 -> 账号或密码错误（INVALID_CREDENTIALS）；
- 1.4 令牌缺失 / 无效 / 过期 -> 未认证（UNAUTHENTICATED）；
- 1.5 存储密码为空 -> 需要重置密码（PASSWORD_RESET_REQUIRED）；
- 1.6 账号 / 密码字段为空 -> 必填字段缺失（MISSING_REQUIRED_FIELD）。

为保证确定性，全部用例使用固定的 aware-UTC ``now``（与 AuthService 的时区处理
约定一致：aware datetime 一律按 UTC 编解码）。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.errors import ErrorCode
from app.core.validators import compute_token_expiry
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.auth_service import ALGORITHM, SECRET_KEY, AuthService

# 固定签发/校验时刻：aware-UTC，保证用例确定性。
NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo() -> Iterator[Repository]:
    """提供绑定到独立内存 SQLite 的 Repository（每个测试隔离）。"""
    engine = create_db_engine()  # 默认内存 SQLite
    create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield Repository(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def service(repo: Repository) -> AuthService:
    """基于隔离仓储构造 AuthService（使用模块级默认密钥/算法）。"""
    return AuthService(repo)


def _create_user(
    repo: Repository,
    *,
    role: str = "Teacher",
    account: str = "alice",
    password: str | None = "secret",
) -> None:
    """便捷创建并提交一个用户。"""
    repo.create_user(role=role, account=account, email="user@example.com", password=password)
    repo.commit()


# --------------------------------------------------------------------------- #
# 登录成功（需求 1.1）                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role", ["Admin", "Teacher", "Student"])
def test_login_success_returns_token_and_role(
    service: AuthService, repo: Repository, role: str
) -> None:
    """正确凭据登录成功：返回 ok、非空令牌，且角色与用户一致（需求 1.1）。"""
    _create_user(repo, role=role, account="alice", password="secret")

    result = service.login("alice", "secret", NOW)

    assert result.ok is True
    assert result.error_code is None
    assert result.token is not None
    assert result.role == role


@pytest.mark.unit
def test_login_success_token_verifies_with_same_role_and_account(
    service: AuthService, repo: Repository
) -> None:
    """登录签发的令牌经 verify_token 校验：返回相同的 role 与 account（需求 1.1）。"""
    _create_user(repo, role="Student", account="bob", password="pw123")

    login = service.login("bob", "pw123", NOW)
    assert login.ok is True and login.token is not None

    verified = service.verify_token(login.token, NOW)
    assert verified.ok is True
    assert verified.error_code is None
    assert verified.role == "Student"
    assert verified.account == "bob"


@pytest.mark.unit
def test_login_success_token_expiry_is_30_minutes_after_now(
    service: AuthService, repo: Repository
) -> None:
    """令牌 exp 声明应恰为签发时刻之后 30 分钟（需求 1.1）。"""
    _create_user(repo, role="Teacher", account="carol", password="pw")

    login = service.login("carol", "pw", NOW)
    assert login.ok is True and login.token is not None

    claims = jwt.decode(
        login.token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"verify_exp": False},
    )

    # exp 以整数 POSIX 时间戳（秒）写入；与 compute_token_expiry(now) 对齐。
    expected_expiry = compute_token_expiry(NOW)
    assert claims["exp"] == int(expected_expiry.timestamp())
    # 等价校验：恰好等于 now + 30min 的时间戳。
    assert claims["exp"] == int((NOW + timedelta(minutes=30)).timestamp())


@pytest.mark.unit
def test_login_success_token_valid_before_expiry_invalid_after(
    service: AuthService, repo: Repository
) -> None:
    """令牌在 now+29min 仍有效，在 now+31min 已过期（需求 1.1 的 30 分钟边界）。"""
    _create_user(repo, role="Admin", account="dave", password="pw")

    login = service.login("dave", "pw", NOW)
    assert login.ok is True and login.token is not None

    # 过期前（now + 29min）仍然有效。
    still_valid = service.verify_token(login.token, NOW + timedelta(minutes=29))
    assert still_valid.ok is True
    assert still_valid.account == "dave"

    # 过期后（now + 31min）判为未认证。
    expired = service.verify_token(login.token, NOW + timedelta(minutes=31))
    assert expired.ok is False
    assert expired.error_code is ErrorCode.UNAUTHENTICATED


# --------------------------------------------------------------------------- #
# 必填字段缺失（需求 1.6）                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    "account,password",
    [
        ("", "pw"),
        ("acc", ""),
        ("", ""),
        ("   ", "pw"),
        ("acc", "   "),
    ],
)
def test_login_missing_required_fields(
    service: AuthService, account: str, password: str
) -> None:
    """账号或密码为空/纯空白 -> MISSING_REQUIRED_FIELD，且不返回令牌（需求 1.6）。"""
    result = service.login(account, password, NOW)

    assert result.ok is False
    assert result.error_code is ErrorCode.MISSING_REQUIRED_FIELD
    assert result.token is None
    assert result.role is None


# --------------------------------------------------------------------------- #
# 凭据错误（需求 1.2）                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_login_wrong_password_returns_invalid_credentials(
    service: AuthService, repo: Repository
) -> None:
    """密码不匹配 -> INVALID_CREDENTIALS，且不返回令牌（需求 1.2）。"""
    _create_user(repo, role="Teacher", account="erin", password="correct")

    result = service.login("erin", "wrong", NOW)

    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_CREDENTIALS
    assert result.token is None


@pytest.mark.unit
def test_login_nonexistent_account_returns_invalid_credentials(
    service: AuthService,
) -> None:
    """账号不存在 -> INVALID_CREDENTIALS，且不返回令牌（需求 1.2）。"""
    result = service.login("ghost", "whatever", NOW)

    assert result.ok is False
    assert result.error_code is ErrorCode.INVALID_CREDENTIALS
    assert result.token is None


# --------------------------------------------------------------------------- #
# 空存储密码需重置（需求 1.5）                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("stored_password", [None, ""])
def test_login_empty_stored_password_requires_reset(
    service: AuthService, repo: Repository, stored_password
) -> None:
    """存储密码为空（None/""）-> PASSWORD_RESET_REQUIRED，且不返回令牌（需求 1.5）。"""
    _create_user(repo, role="Student", account="frank", password=stored_password)

    result = service.login("frank", "anything", NOW)

    assert result.ok is False
    assert result.error_code is ErrorCode.PASSWORD_RESET_REQUIRED
    assert result.token is None


# --------------------------------------------------------------------------- #
# 令牌校验失败（需求 1.4）                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    "token",
    [None, "", "   ", "not-a-jwt", "abc.def.ghi"],
)
def test_verify_token_missing_or_garbage_unauthenticated(
    service: AuthService, token
) -> None:
    """令牌缺失或无法解析 -> UNAUTHENTICATED（需求 1.4）。"""
    result = service.verify_token(token, NOW)

    assert result.ok is False
    assert result.error_code is ErrorCode.UNAUTHENTICATED
    assert result.role is None
    assert result.account is None


@pytest.mark.unit
def test_verify_token_expired_unauthenticated(
    service: AuthService, repo: Repository
) -> None:
    """已过期令牌（now 超过 exp）-> UNAUTHENTICATED（需求 1.4）。"""
    _create_user(repo, role="Teacher", account="grace", password="pw")

    login = service.login("grace", "pw", NOW)
    assert login.ok is True and login.token is not None

    # 令牌在 now + 30min 处达到 exp，1 小时后必然已过期。
    result = service.verify_token(login.token, NOW + timedelta(hours=1))

    assert result.ok is False
    assert result.error_code is ErrorCode.UNAUTHENTICATED
