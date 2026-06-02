"""API 认证依赖与中间件辅助的单元测试（任务 16.1）。

覆盖 ``app.api.deps`` 与 ``app.api.middleware`` 的认证接线（需求 1.3, 1.4）：

- 有效令牌 -> 注入 ``CurrentUser(role, account)``（需求 1.3）；
- 令牌缺失 / 格式错误 / 无效 / 过期 -> ``401 UNAUTHENTICATED``（需求 1.4）；
- ``require_roles`` 角色匹配放行、不匹配 -> ``403 FORBIDDEN``（需求 1.3）；
- ``parse_bearer_token`` 的解析规则。

测试通过 ``app.dependency_overrides`` 将认证服务/时钟绑定到隔离的内存 SQLite
仓储与确定性时间，避免依赖模块级默认引擎，从而保证用例相互隔离且可重复。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import CurrentUser, get_auth_service, get_current_user, require_roles, utcnow
from app.api.middleware import parse_bearer_token
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.auth_service import AuthService

# 固定签发/校验时刻：aware-UTC，保证用例确定性。
NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# parse_bearer_token 解析规则                                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    "header,expected",
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer abc", "abc"),  # 方案名不区分大小写
        ("BEARER xyz", "xyz"),
        ("Bearer    spaced", "spaced"),  # 折叠多余空白
        (None, None),  # 缺失
        ("", None),  # 空串
        ("Bearer", None),  # 只有方案、无令牌
        ("Bearer    ", None),  # 令牌为空白
        ("Token abc", None),  # 非 Bearer 方案
        ("abc.def.ghi", None),  # 缺少方案
    ],
)
def test_parse_bearer_token(header, expected) -> None:
    """parse_bearer_token 按 'Bearer <token>' 规则解析，否则返回 None。"""
    assert parse_bearer_token(header) == expected


# --------------------------------------------------------------------------- #
# 测试用 FastAPI 应用与依赖覆盖                                                  #
# --------------------------------------------------------------------------- #


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
def client(repo: Repository) -> Iterator[TestClient]:
    """构造带受保护路由的应用，并将认证服务/时钟覆盖为隔离仓储与固定 NOW。"""
    app = FastAPI()

    @app.get("/me")
    def read_me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"role": user.role, "account": user.account}

    @app.get("/teacher-only")
    def teacher_only(
        user: CurrentUser = Depends(require_roles("Teacher")),
    ) -> dict[str, str]:
        return {"role": user.role, "account": user.account}

    @app.get("/staff-only")
    def staff_only(
        user: CurrentUser = Depends(require_roles("Admin", "Teacher")),
    ) -> dict[str, str]:
        return {"role": user.role, "account": user.account}

    # 覆盖认证服务，使其使用隔离仓储；覆盖时钟为固定 NOW（确定性）。
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repo)
    app.dependency_overrides[utcnow] = lambda: NOW

    with TestClient(app) as test_client:
        yield test_client


def _issue_token(repo: Repository, *, role: str, account: str) -> str:
    """创建用户并签发一个在 NOW 时刻有效的令牌。"""
    repo.create_user(role=role, account=account, email="u@example.com", password="pw")
    repo.commit()
    login = AuthService(repo).login(account, "pw", NOW)
    assert login.ok is True and login.token is not None
    return login.token


# --------------------------------------------------------------------------- #
# get_current_user：有效令牌注入（需求 1.3）                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize("role", ["Admin", "Teacher", "Student"])
def test_valid_token_injects_current_user(
    client: TestClient, repo: Repository, role: str
) -> None:
    """有效 Bearer 令牌 -> 注入正确的 role 与 account（需求 1.3）。"""
    token = _issue_token(repo, role=role, account="alice")

    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json() == {"role": role, "account": "alice"}


# --------------------------------------------------------------------------- #
# get_current_user：缺失/无效/过期 -> 401（需求 1.4）                            #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_missing_token_returns_401(client: TestClient) -> None:
    """无 Authorization 头 -> 401 UNAUTHENTICATED（需求 1.4）。"""
    resp = client.get("/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "UNAUTHENTICATED"


@pytest.mark.unit
@pytest.mark.parametrize(
    "header",
    ["Bearer not-a-jwt", "Token abc", "Bearer ", "Bearer abc.def.ghi"],
)
def test_invalid_token_returns_401(client: TestClient, header: str) -> None:
    """格式错误/无法解析的令牌 -> 401 UNAUTHENTICATED（需求 1.4）。"""
    resp = client.get("/me", headers={"Authorization": header})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "UNAUTHENTICATED"


@pytest.mark.unit
def test_expired_token_returns_401(repo: Repository) -> None:
    """已过期令牌（now 超过 exp）-> 401 UNAUTHENTICATED（需求 1.4）。"""
    app = FastAPI()

    @app.get("/me")
    def read_me(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"role": user.role, "account": user.account}

    token = _issue_token(repo, role="Teacher", account="bob")
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repo)
    # 时钟拨到 exp（NOW + 30min）之后，令牌必然过期。
    app.dependency_overrides[utcnow] = lambda: NOW + timedelta(hours=1)

    with TestClient(app) as test_client:
        resp = test_client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "UNAUTHENTICATED"


# --------------------------------------------------------------------------- #
# require_roles：角色门控（需求 1.3）                                            #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_require_roles_allows_matching_role(client: TestClient, repo: Repository) -> None:
    """角色匹配 -> 放行进入业务逻辑（需求 1.3）。"""
    token = _issue_token(repo, role="Teacher", account="teach")
    resp = client.get("/teacher-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "Teacher"


@pytest.mark.unit
def test_require_roles_rejects_other_role_with_403(
    client: TestClient, repo: Repository
) -> None:
    """角色不匹配 -> 403 FORBIDDEN（需求 1.3）。"""
    token = _issue_token(repo, role="Student", account="stud")
    resp = client.get("/teacher-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error_code"] == "FORBIDDEN"


@pytest.mark.unit
def test_require_roles_missing_token_returns_401(client: TestClient) -> None:
    """受角色保护的资源在无令牌时仍先返回 401（认证先于授权）（需求 1.4）。"""
    resp = client.get("/teacher-only")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "UNAUTHENTICATED"


@pytest.mark.unit
def test_require_roles_supports_multiple_roles(client: TestClient, repo: Repository) -> None:
    """多角色门控：集合内任一角色均放行（需求 1.3）。"""
    token = _issue_token(repo, role="Admin", account="root")
    resp = client.get("/staff-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "Admin"


# --------------------------------------------------------------------------- #
# utcnow 默认返回 aware-UTC                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_utcnow_is_aware_utc() -> None:
    """utcnow 返回带 UTC 时区的 aware datetime（与 verify_token 约定一致）。"""
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
