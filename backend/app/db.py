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
    """依据全部 ORM 模型的元数据在目标库中创建表，并执行轻量列迁移。"""
    # 延迟导入模型以确保其在元数据中完成注册，同时避免模块级循环导入。
    from app import models  # noqa: F401  (import for side effect: model registration)

    Base.metadata.create_all(engine)
    _run_lightweight_migrations(engine)


def _run_lightweight_migrations(engine: Engine) -> None:
    """为已存在的旧库补充新增列、移除过时约束（幂等）。

    ``create_all`` 不会修改已存在表的结构，因此对旧库需手动迁移：

    1. 为 ``users`` 表补充 ``email_verified`` 列（默认 0=未验证）。
    2. 移除 ``users`` 表上过时的全局唯一约束（``uq_users_account`` /
       ``uq_users_student_id``）——新模型允许学号跨校重复、account 由应用层按角色
       校验唯一。SQLite 无法直接 DROP 约束，故通过「建新表 -> 拷贝数据 -> 替换」重建。
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("users")}
    if "email_verified" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0")
            )
    if "avatar" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar TEXT"))

    # 检测过时唯一约束，若存在则重建 users 表（仅 SQLite 需要此处理）。
    if engine.dialect.name == "sqlite":
        uniques = {uc["name"] for uc in inspect(engine).get_unique_constraints("users")}
        if {"uq_users_account", "uq_users_student_id"} & uniques:
            _rebuild_users_table_without_unique(engine)


def _rebuild_users_table_without_unique(engine: Engine) -> None:
    """重建 SQLite ``users`` 表以移除过时唯一约束，保留全部数据。"""
    from sqlalchemy import text

    with engine.begin() as conn:
        # 读取现有列顺序，保证拷贝时列对齐。
        rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        col_names = [r[1] for r in rows]
        cols_csv = ", ".join(col_names)
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("ALTER TABLE users RENAME TO users_old"))
        # 依据当前模型重新建表（无 account/student_id 唯一约束）。
        Base.metadata.tables["users"].create(bind=conn)
        conn.execute(
            text(f"INSERT INTO users ({cols_csv}) SELECT {cols_csv} FROM users_old")
        )
        conn.execute(text("DROP TABLE users_old"))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def drop_all(engine: Engine) -> None:
    """删除全部 ORM 模型对应的表（主要用于测试清理）。"""
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
