"""项目骨架冒烟测试：验证应用可导入且健康检查端点可用。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.main import app, create_app


@pytest.mark.unit
def test_app_module_importable() -> None:
    """`app.main` 可被导入且暴露 FastAPI 应用实例。"""
    assert app is not None
    assert app.title


@pytest.mark.unit
def test_create_app_returns_fresh_instance() -> None:
    """应用工厂每次返回独立实例，便于测试隔离。"""
    a = create_app()
    b = create_app()
    assert a is not b


@pytest.mark.unit
def test_health_endpoint_reports_ok() -> None:
    """健康检查端点返回 ok 状态与版本号。"""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
