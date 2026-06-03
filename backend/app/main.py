"""FastAPI 应用骨架。

提供应用工厂、健康检查端点、CORS 中间件、业务路由接入。
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import load_app_env

# 尽早加载 .env（在导入依赖/路由前），确保存储、邮件等读取到正确配置。
load_app_env()

from app.api.routes import ALL_ROUTERS

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

    return app


app = create_app()
