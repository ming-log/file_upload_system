"""API 路由包（task 16.2）。

按业务资源拆分为独立模块，每个模块导出一个 :class:`fastapi.APIRouter`：

* :mod:`app.api.routes.auth` —— 登录（公共端点，无需认证）。
* :mod:`app.api.routes.users` —— 教师创建、通用用户创建、批量创建。
* :mod:`app.api.routes.classes` —— 班级创建/列表、班级内学生创建/导入。
* :mod:`app.api.routes.courses` —— 课程创建/列表。
* :mod:`app.api.routes.assignments` —— 作业创建/列表。
* :mod:`app.api.routes.submissions` —— 学生作业提交（multipart 文件上传）。

:func:`app.main.create_app` 通过 :data:`ALL_ROUTERS` 统一接入全部路由。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.assignments import router as assignments_router
from app.api.routes.auth import router as auth_router
from app.api.routes.classes import router as classes_router
from app.api.routes.courses import router as courses_router
from app.api.routes.me import router as me_router
from app.api.routes.submissions import router as submissions_router
from app.api.routes.users import router as users_router

__all__ = ["ALL_ROUTERS"]

#: 应用工厂据此顺序接入全部业务路由。
ALL_ROUTERS: list[APIRouter] = [
    auth_router,
    me_router,
    users_router,
    classes_router,
    courses_router,
    assignments_router,
    submissions_router,
]
