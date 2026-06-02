"""API 路由与错误码映射的集成测试（任务 16.2）。

通过 :class:`fastapi.testclient.TestClient` 与依赖覆盖，端到端验证各业务路由
与 :mod:`app.api.errors` 的错误码到 HTTP 映射：

* ``get_repository`` 覆盖为绑定到**隔离内存 SQLite** 的共享 Repository，使
  种子数据与路由处理共享同一会话/事务边界；
* ``get_storage_service`` 覆盖为 :class:`~app.adapters.storage_service.FakeStorageService`，
  无需真实 MinIO 即可验证提交流程；
* ``get_email_service`` 覆盖为注入 no-op 发送器/休眠的 :class:`EmailService`，
  避免提交成功后异步通知触发真实 SMTP I/O。

覆盖场景：登录成功返回令牌；未认证访问受保护路由 -> 401；角色不匹配 -> 403；
创建班级/课程/作业 happy path 返回标识；学生提交 happy path 返回 200；并抽样
验证若干错误码 -> HTTP 状态映射（如截止时间无效 400、扩展名不被允许 400）。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.adapters.email_service import EmailService
from app.adapters.storage_service import FakeStorageService
from app.api.deps import (
    get_email_service,
    get_repository,
    get_storage_service,
)
from app.db import Base, create_session_factory
from app.main import create_app
from app.repository import Repository
from app.services.auth_service import AuthService

FUTURE_DEADLINE = "2999-01-01T00:00:00"


async def _noop_sender(recipient: str, body: str) -> None:
    """no-op「单次发送」：避免提交成功后的异步通知触发真实 SMTP。"""
    return None


async def _noop_sleep(_seconds: float) -> None:
    """no-op 异步休眠：测试中不真实等待。"""
    return None


@pytest.fixture()
def repo() -> Iterator[Repository]:
    """绑定到独立内存 SQLite 的共享 Repository（每个测试隔离）。

    使用 ``StaticPool`` + ``check_same_thread=False`` 让同一个内存数据库连接
    在所有线程间复用：``TestClient`` 会在工作线程中执行同步路由处理函数，而
    种子数据在测试主线程写入；若使用默认的线程级连接池，二者会落入不同的内存
    库（导致 "no such table"）。``StaticPool`` 确保全程共用同一连接与同一库。
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # 确保模型在元数据中注册后再建表。
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        yield Repository(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def storage() -> FakeStorageService:
    """供注入的内存存储服务。"""
    return FakeStorageService()


@pytest.fixture()
def client(repo: Repository, storage: FakeStorageService) -> Iterator[TestClient]:
    """构造应用并覆盖仓储/存储/邮件依赖为隔离实例。"""
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_email_service] = lambda: EmailService(
        sender=_noop_sender, sleep=_noop_sleep
    )
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------- #
# 种子数据与令牌辅助                                                            #
# --------------------------------------------------------------------------- #


def _seed_user(repo: Repository, *, role: str, account: str, **kwargs: object) -> None:
    repo.create_user(role=role, account=account, password="pw", **kwargs)  # type: ignore[arg-type]
    repo.commit()


def _token(repo: Repository, account: str) -> str:
    result = AuthService(repo).login(account, "pw", _now(repo))
    assert result.ok and result.token is not None
    return result.token


def _now(repo: Repository):
    # 复用 deps.utcnow 的语义：aware-UTC 当前时间。
    from app.api.deps import utcnow

    return utcnow()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# 登录                                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_login_success_returns_token(client: TestClient, repo: Repository) -> None:
    """登录成功返回 access_token、token_type、role、account（需求 1.1/1.3）。"""
    _seed_user(repo, role="Teacher", account="teacher", email="t@example.com")
    resp = client.post(
        "/auth/login", json={"account": "teacher", "password": "pw"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["role"] == "Teacher"
    assert body["account"] == "teacher"


@pytest.mark.integration
def test_login_wrong_password_maps_to_401(client: TestClient, repo: Repository) -> None:
    """凭据错误 -> 401 INVALID_CREDENTIALS（需求 1.2）。"""
    _seed_user(repo, role="Teacher", account="teacher", email="t@example.com")
    resp = client.post(
        "/auth/login", json={"account": "teacher", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"


# --------------------------------------------------------------------------- #
# 认证 / 授权门控                                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_protected_route_without_token_returns_401(client: TestClient) -> None:
    """未携带令牌访问受保护路由 -> 401 UNAUTHENTICATED（需求 1.4）。"""
    resp = client.get("/classes")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "UNAUTHENTICATED"


@pytest.mark.integration
def test_role_gated_route_returns_403_for_wrong_role(
    client: TestClient, repo: Repository
) -> None:
    """学生访问仅教师可用的创建班级路由 -> 403 FORBIDDEN（需求 5.2）。"""
    _seed_user(
        repo,
        role="Student",
        account="S001",
        email="s@example.com",
        student_id="S001",
        name="小明",
    )
    token = _token(repo, "S001")
    resp = client.post(
        "/classes",
        headers=_auth(token),
        json={"school": "清华", "grade": "2024", "major": "CS"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error_code"] == "FORBIDDEN"


# --------------------------------------------------------------------------- #
# 创建 happy path：班级 / 课程 / 作业                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_create_class_course_assignment_happy_path(
    client: TestClient, repo: Repository
) -> None:
    """教师依次创建班级、课程、作业，均返回非空标识。"""
    _seed_user(repo, role="Teacher", account="teacher", email="t@example.com")
    token = _token(repo, "teacher")

    # 创建班级。
    resp = client.post(
        "/classes",
        headers=_auth(token),
        json={"school": "清华", "grade": "2024", "major": "CS"},
    )
    assert resp.status_code == 200, resp.text
    class_id = resp.json()["id"]
    assert class_id

    # 创建课程，关联到该班级。
    resp = client.post(
        "/courses",
        headers=_auth(token),
        json={"semester": "2024秋", "name": "软件工程", "class_id": class_id},
    )
    assert resp.status_code == 200, resp.text
    course_id = resp.json()["id"]
    assert course_id

    # 创建作业，关联到该课程。
    resp = client.post(
        "/assignments",
        headers=_auth(token),
        json={
            "title": "第一次作业",
            "content": "请提交报告",
            "course_id": course_id,
            "allowed_extensions": ["pdf"],
            "max_file_size_mb": 5,
            "deadline": FUTURE_DEADLINE,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"]


@pytest.mark.integration
def test_create_assignment_invalid_deadline_maps_to_400(
    client: TestClient, repo: Repository
) -> None:
    """截止时间不晚于当前 -> 400 INVALID_DEADLINE（需求 8.13）。"""
    _seed_user(repo, role="Teacher", account="teacher", email="t@example.com")
    token = _token(repo, "teacher")
    resp = client.post(
        "/classes",
        headers=_auth(token),
        json={"school": "清华", "grade": "2024", "major": "CS"},
    )
    class_id = resp.json()["id"]
    resp = client.post(
        "/courses",
        headers=_auth(token),
        json={"semester": "2024秋", "name": "软件工程", "class_id": class_id},
    )
    course_id = resp.json()["id"]
    resp = client.post(
        "/assignments",
        headers=_auth(token),
        json={
            "title": "过期作业",
            "content": "",
            "course_id": course_id,
            "allowed_extensions": ["pdf"],
            "max_file_size_mb": 5,
            "deadline": "2000-01-01T00:00:00",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "INVALID_DEADLINE"


# --------------------------------------------------------------------------- #
# 学生提交 happy path 与错误映射                                                #
# --------------------------------------------------------------------------- #


def _setup_assignment(client: TestClient, repo: Repository) -> str:
    """以教师身份创建班级/课程/作业，返回作业标识。"""
    _seed_user(repo, role="Teacher", account="teacher", email="t@example.com")
    t = _token(repo, "teacher")
    class_id = client.post(
        "/classes",
        headers=_auth(t),
        json={"school": "清华", "grade": "2024", "major": "CS"},
    ).json()["id"]
    course_id = client.post(
        "/courses",
        headers=_auth(t),
        json={"semester": "2024秋", "name": "软件工程", "class_id": class_id},
    ).json()["id"]
    assignment_id = client.post(
        "/assignments",
        headers=_auth(t),
        json={
            "title": "第一次作业",
            "content": "请提交报告",
            "course_id": course_id,
            "allowed_extensions": ["pdf"],
            "max_file_size_mb": 5,
            "deadline": FUTURE_DEADLINE,
        },
    ).json()["id"]
    return assignment_id


@pytest.mark.integration
def test_student_submission_happy_path_returns_200(
    client: TestClient, repo: Repository, storage: FakeStorageService
) -> None:
    """学生提交合法文件 -> 200，返回提交标识/文件名/时间，并写入 FakeStorage。"""
    assignment_id = _setup_assignment(client, repo)
    _seed_user(
        repo,
        role="Student",
        account="S001",
        email="s@example.com",
        student_id="S001",
        name="小明",
    )
    token = _token(repo, "S001")

    resp = client.post(
        f"/assignments/{assignment_id}/submissions",
        headers=_auth(token),
        files={"file": ("report.pdf", b"hello world", "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"]
    assert body["file_name"] == "report.pdf"
    # 文件已写入 FakeStorageService，且恰好保存一次（0 重试）。
    assert storage.save_call_count == 1
    assert len(storage.objects) == 1


@pytest.mark.integration
def test_student_submission_wrong_extension_maps_to_400(
    client: TestClient, repo: Repository
) -> None:
    """提交不被允许的扩展名 -> 400 EXTENSION_NOT_ALLOWED（需求 9.4）。"""
    assignment_id = _setup_assignment(client, repo)
    _seed_user(
        repo,
        role="Student",
        account="S001",
        email="s@example.com",
        student_id="S001",
        name="小明",
    )
    token = _token(repo, "S001")

    resp = client.post(
        f"/assignments/{assignment_id}/submissions",
        headers=_auth(token),
        files={"file": ("malware.exe", b"hello world", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "EXTENSION_NOT_ALLOWED"


@pytest.mark.integration
def test_student_submission_storage_failure_maps_to_502(
    client: TestClient, repo: Repository, storage: FakeStorageService
) -> None:
    """存储失败 -> 502 STORAGE_FAILED，且不创建提交记录（需求 10.3）。"""
    assignment_id = _setup_assignment(client, repo)
    _seed_user(
        repo,
        role="Student",
        account="S001",
        email="s@example.com",
        student_id="S001",
        name="小明",
    )
    token = _token(repo, "S001")
    storage.set_mode(fail=True)

    resp = client.post(
        f"/assignments/{assignment_id}/submissions",
        headers=_auth(token),
        files={"file": ("report.pdf", b"hello world", "application/pdf")},
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["error_code"] == "STORAGE_FAILED"
    # 0 重试：仅尝试一次。
    assert storage.save_call_count == 1
