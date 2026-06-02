"""数据库引擎、会话工厂与声明式基类。

本模块提供最小化的持久化基础设施：

* :class:`Base` —— 所有 ORM 模型共享的声明式基类（SQLAlchemy 2.x 风格）。
* :func:`create_db_engine` —— 构造 :class:`~sqlalchemy.engine.Engine`，默认指向
  内存 SQLite，便于测试；生产可传入 MySQL/PostgreSQL 连接串。
* :func:`create_session_factory` —— 基于引擎构造 :class:`sessionmaker`。
* :func:`create_all` / :func:`drop_all` —— 依据模型元数据创建/删除全部表。

后续仓储层（task 4.2）将复用这里的会话工厂与基类，因此本模块刻意保持精简，
不绑定任何具体业务逻辑。
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

__all__ = [
    "Base",
    "DEFAULT_DATABASE_URL",
    "create_db_engine",
    "create_session_factory",
    "create_all",
    "drop_all",
]


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。

    采用 SQLAlchemy 2.x 推荐的 :class:`DeclarativeBase` + ``Mapped`` /
    ``mapped_column`` 注解式映射风格。
    """


# 默认使用内存 SQLite，零依赖、适合单元/属性测试。
DEFAULT_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def create_db_engine(database_url: str = DEFAULT_DATABASE_URL, *, echo: bool = False) -> Engine:
    """创建数据库引擎。

    Args:
        database_url: SQLAlchemy 连接串。默认指向内存 SQLite。
        echo: 是否回显 SQL 语句，调试时可置为 ``True``。

    Returns:
        已配置的 :class:`~sqlalchemy.engine.Engine` 实例。
    """
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # SQLite 在多线程场景需要放宽线程检查（如 FastAPI/TestClient）。
        connect_args["check_same_thread"] = False
        # 内存 SQLite（``:memory:``）每个连接都是独立的数据库；在多线程/连接池
        # 场景下，不同连接会看到不同的空库（导致 "no such table"）。使用
        # StaticPool 让全程共用同一连接与同一内存库，使建表与播种的数据对所有
        # 请求线程可见。基于文件的 SQLite 与其它数据库不受影响。
        if ":memory:" in database_url or "mode=memory" in database_url:
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(
        database_url,
        echo=echo,
        future=True,
        connect_args=connect_args,
        **engine_kwargs,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """基于引擎构造会话工厂。"""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
        class_=Session,
    )


def create_all(engine: Engine) -> None:
    """依据全部 ORM 模型的元数据在目标库中创建表。"""
    # 延迟导入模型以确保其在元数据中完成注册，同时避免模块级循环导入。
    from app import models  # noqa: F401  (import for side effect: model registration)

    Base.metadata.create_all(engine)


def drop_all(engine: Engine) -> None:
    """删除全部 ORM 模型对应的表（主要用于测试清理）。"""
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
