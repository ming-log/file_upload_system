"""运行时配置加载。

集中负责从项目根目录的 ``.env`` 文件加载环境变量到 ``os.environ``，使其余模块
（存储、邮件、认证等）可继续通过 :func:`os.getenv` 读取配置，无需改动各自的读取
方式。``.env`` 含敏感信息（MinIO / SMTP 凭据），已被 ``.gitignore`` 忽略。

加载策略：
* 使用 python-dotenv 的 :func:`load_dotenv` 读取 ``backend/.env``；
* ``override=False`` —— 已存在的真实环境变量优先，``.env`` 仅作为缺省补充，便于
  在容器 / CI 中通过环境变量覆盖；
* 幂等：:func:`load_app_env` 仅在进程内加载一次。

本模块在 :mod:`app.main` 与 :mod:`app.api.deps` 顶部尽早导入并调用
:func:`load_app_env`，确保后续读取环境变量时 ``.env`` 已生效。
"""

from __future__ import annotations

import os

__all__ = ["ENV_PATH", "load_app_env"]

# backend/ 目录下的 .env 路径（本文件位于 backend/app/config.py）。
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

_loaded = False


def load_app_env() -> None:
    """从 ``backend/.env`` 加载环境变量（幂等；真实环境变量优先）。

    若未安装 python-dotenv 或文件不存在，则静默跳过（不影响通过真实环境变量
    或默认值运行）。
    """
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        from dotenv import load_dotenv
    except Exception:  # pragma: no cover - 缺少依赖时回退到纯环境变量
        return
    if os.path.isfile(ENV_PATH):
        load_dotenv(ENV_PATH, override=False)
