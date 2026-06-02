"""FastAPI 应用骨架。

提供应用工厂、健康检查端点、CORS 中间件、业务路由接入，以及启动时的演示数据播种
（开发/本地联调用，使空库也能直接登录）。
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.deps import _session_factory
from app.api.routes import ALL_ROUTERS
from app.seed import seed_initial_data

logger = logging.getLogger(__name__)

API_TITLE = "作业文件上传系统 API"
API_DESCRIPTION = "前后端分离的作业文件上传系统后端服务（FastAPI）。"

#: 允许的前端来源。可经环境变量 CORS_ORIGINS（逗号分隔）覆盖；缺省放开本地开发端口。
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    """应用工厂：构造并返回配置好的 FastAPI 实例。"""
    app = FastAPI(title=API_TITLE, description=API_DESCRIPTION, version=__version__)

    # CORS：允许前端（Vite dev server）跨域访问。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["infra"], summary="健康检查")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    for router in ALL_ROUTERS:
        app.include_router(router)

    @app.on_event("startup")
    def _seed_on_startup() -> None:
        if os.getenv("SEED_DISABLE", "").strip().lower() in {"1", "true", "yes"}:
            return
        session = _session_factory()
        try:
            seed_initial_data(session)
        except Exception:  # 播种失败不应阻断应用启动
            logger.warning("初始数据播种失败（应用仍正常启动）", exc_info=True)
        finally:
            session.close()

    return app


app = create_app()
