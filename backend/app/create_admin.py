"""创建初始管理员账号（CLI 工具）。

系统不再在启动时自动播种演示数据，因此全新部署的数据库中没有任何可登录账号。
本模块提供一个一次性命令，用于安全地创建首个管理员账号，登录后即可在管理端创建
教师、班级、课程、学生等业务数据。

用法::

    # 通过命令行参数（注意：明文密码可能残留在 shell 历史中，慎用）
    python -m app.create_admin --account admin --email admin@example.com --password <pwd>

    # 通过环境变量
    set ADMIN_ACCOUNT=admin && set ADMIN_PASSWORD=<pwd> && python -m app.create_admin

    # 交互式输入密码（推荐：不会泄露到命令行历史）
    python -m app.create_admin --account admin --email admin@example.com

行为说明：

* 数据库连接串复用应用逻辑：优先环境变量 ``DATABASE_URL``，缺省回退到
  ``backend/homework.db``（文件 SQLite）。
* **幂等**：若目标账号已存在，或系统内已存在任意管理员，则跳过创建并提示。
* 密码以明文存储（与现有登录校验逻辑一致），请使用强密码并妥善保管。
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.config import load_app_env
from app.core.clock import now_cn_naive
from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository

#: 默认数据库连接串：与 app.api.deps 保持一致（文件 SQLite，持久化）。
_DEFAULT_SQLITE = "sqlite+pysqlite:///./homework.db"


def _resolve_password(cli_password: str | None) -> str:
    """按优先级解析管理员密码：命令行参数 > 环境变量 > 交互式输入。

    交互式输入要求两次一致；任一来源得到的密码为空均视为无效。
    """
    if cli_password:
        return cli_password
    env_password = os.getenv("ADMIN_PASSWORD")
    if env_password:
        return env_password
    # 交互式：两次输入并比对，避免误输。
    first = getpass.getpass("请输入管理员密码: ")
    second = getpass.getpass("请再次输入以确认: ")
    if first != second:
        print("两次输入的密码不一致。", file=sys.stderr)
        raise SystemExit(2)
    return first


def create_initial_admin(
    *,
    account: str,
    password: str,
    email: str,
    name: str,
    database_url: str,
) -> int:
    """创建初始管理员账号（幂等）。

    Returns:
        进程退出码：``0`` 表示创建成功或已存在（无需处理）；非 0 表示参数错误。
    """
    if not account.strip():
        print("账号不能为空。", file=sys.stderr)
        return 2
    if not password:
        print("密码不能为空。", file=sys.stderr)
        return 2

    engine = create_db_engine(database_url)
    create_all(engine)
    session_factory = create_session_factory(engine)

    session = session_factory()
    try:
        repo = Repository(session)

        # 幂等：账号已存在则跳过。
        if repo.get_user_by_account(account) is not None:
            print(f"账号 '{account}' 已存在，跳过创建。")
            return 0
        # 幂等：系统内已存在任意管理员则跳过（避免重复创建多个初始管理员）。
        if repo.list_users(roles=["admin"]):
            print("系统内已存在管理员账号，跳过创建。")
            return 0

        with repo.transaction():
            repo.create_user(
                role="admin",
                account=account,
                name=name,
                email=email,
                password=password,
                created_at=now_cn_naive(),
            )
        print(f"已创建管理员账号：{account}")
        return 0
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    load_app_env()

    parser = argparse.ArgumentParser(
        prog="python -m app.create_admin",
        description="创建初始管理员账号（幂等）。",
    )
    parser.add_argument(
        "--account",
        default=os.getenv("ADMIN_ACCOUNT", "admin"),
        help="管理员登录账号（默认取环境变量 ADMIN_ACCOUNT，否则为 'admin'）。",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        help="管理员邮箱（默认取环境变量 ADMIN_EMAIL）。",
    )
    parser.add_argument(
        "--name",
        default=os.getenv("ADMIN_NAME", "系统管理员"),
        help="管理员姓名（默认 '系统管理员'）。",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="管理员密码；缺省时改用环境变量 ADMIN_PASSWORD 或交互式输入。",
    )
    args = parser.parse_args(argv)

    password = _resolve_password(args.password)
    database_url = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)

    return create_initial_admin(
        account=args.account,
        password=password,
        email=args.email,
        name=args.name,
        database_url=database_url,
    )


if __name__ == "__main__":
    raise SystemExit(main())
