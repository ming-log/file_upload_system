from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.adapters.email_service import EmailService
from app.api.deps import get_email_service, get_email_verification_service, get_repository, now_provider
from app.db import Base, create_session_factory
from app.main import create_app
from app.repository import Repository
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService


@pytest.fixture()
def repo() -> Iterator[Repository]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        yield Repository(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def sent_messages() -> list[str]:
    return []


@pytest.fixture()
def client(repo: Repository, sent_messages: list[str]) -> Iterator[TestClient]:
    async def sender(recipient: str, _body: str) -> None:
        sent_messages.append(recipient)

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_email_service] = lambda: EmailService(sender=sender)
    app.dependency_overrides[get_email_verification_service] = EmailVerificationService
    with TestClient(app) as test_client:
        yield test_client


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _teacher_token_and_class(repo: Repository) -> tuple[str, str]:
    with repo.transaction():
        teacher = repo.create_user(
            role="teacher",
            account="teacher",
            name="Teacher",
            email="teacher@example.com",
            password="pw",
        )
        clazz = repo.create_class(
            school="清华",
            grade="2026",
            major="软件工程",
            teacher_id=teacher.id,
        )
    token = AuthService(repo).login("teacher", "pw", now_provider()).token
    assert token is not None
    return token, clazz.id


@pytest.mark.integration
def test_create_student_allows_empty_email(client: TestClient, repo: Repository) -> None:
    token, class_id = _teacher_token_and_class(repo)

    resp = client.post(
        f"/classes/{class_id}/students",
        headers=_auth(token),
        json={"studentId": "S001", "name": "张三", "email": "", "password": ""},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == ""
    assert body["emailVerified"] is False
    stored = repo.get_student_by_school_and_id("清华", "S001")
    assert stored is not None
    assert stored.email is None


@pytest.mark.integration
def test_create_student_rejects_invalid_non_empty_email(
    client: TestClient, repo: Repository
) -> None:
    token, class_id = _teacher_token_and_class(repo)

    resp = client.post(
        f"/classes/{class_id}/students",
        headers=_auth(token),
        json={"studentId": "S001", "name": "张三", "email": "bad-email", "password": ""},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "INVALID_EMAIL_FORMAT"


@pytest.mark.integration
def test_student_send_code_binds_email_when_missing(
    client: TestClient, repo: Repository, sent_messages: list[str]
) -> None:
    with repo.transaction():
        teacher = repo.create_user(role="teacher", account="teacher", password="pw")
        clazz = repo.create_class(
            school="清华",
            grade="2026",
            major="软件工程",
            teacher_id=teacher.id,
        )
        repo.create_user(
            role="student",
            account="S001",
            name="张三",
            email=None,
            password="pw",
            student_id="S001",
            class_id=clazz.id,
        )
    token = AuthService(repo).login_student("清华", "S001", "pw", now_provider()).token
    assert token is not None

    resp = client.post(
        "/auth/email/send-code",
        headers=_auth(token),
        json={"email": "student@example.com"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "s***@example.com"
    assert sent_messages == ["student@example.com"]
    stored = repo.get_student_by_school_and_id("清华", "S001")
    assert stored is not None
    assert stored.email == "student@example.com"
    assert stored.email_verified is False
