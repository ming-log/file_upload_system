# Feature: homework-upload-system, Property 3: 登录成功的令牌角色与用户角色一致
"""Property 3: 登录成功的令牌角色与用户角色一致。

依据 design.md「Correctness Properties」Property 3：

    *For any* 已存储的用户与其正确凭据，登录成功后返回令牌中的 ``role``
    应等于该用户实际的 ``role``。

**Validates: Requirements 1.3**

测试策略
--------

* 每个 Hypothesis 样例在测试体内构建一个全新的内存 SQLite 引擎与
  :class:`~app.repository.Repository`，确保样例之间互不干扰。
* 采样合法角色（Admin / Teacher / Student），生成非空白账号与非空密码，
  通过 :meth:`Repository.create_user` 写入并提交。
* 调用 :meth:`AuthService.login` 完成登录，断言：
    1. 登录成功且返回了令牌（``result.ok`` 且 ``result.token is not None``）；
    2. ``result.role`` 等于该用户的实际角色；
    3. 解码令牌后其 ``role`` 声明同样等于该用户的实际角色（需求 1.3）。
  其中第 3 步分别通过 :func:`jose.jwt.decode`（关闭 ``exp`` 校验）直接读取
  ``role`` 声明，以及调用 :meth:`AuthService.verify_token` 两种途径交叉验证。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jose import jwt

from app.db import create_all, create_db_engine, create_session_factory
from app.repository import Repository
from app.services.auth_service import ALGORITHM, SECRET_KEY, AuthService

# 合法角色集合（design.md Data Models：role ∈ {Admin, Teacher, Student}）。
_ROLES = ["Admin", "Teacher", "Student"]

# 非空白字符串：login 中 validate_required 要求账号/密码 strip 后非空。
# 限制长度以贴合模型存储宽度（account ≤ 64、password ≤ 255）。
_account_strategy = st.text(min_size=1, max_size=64).filter(lambda s: s.strip() != "")
_password_strategy = st.text(min_size=1, max_size=255).filter(lambda s: s.strip() != "")

# 登录时刻 now：约束在现实可表示的时间窗口内（1970..2100）。
# 该约束排除了 datetime.fromtimestamp 在部分平台（如 Windows）无法处理的
# 负 POSIX 时间戳（1970 年以前），使生成器贴合“当前登录时间”的真实输入空间，
# 不影响对 Property 3（令牌角色与用户角色一致）的验证。
_now_strategy = st.datetimes(
    min_value=datetime(1970, 1, 2),
    max_value=datetime(2100, 1, 1),
)


def _fresh_repository() -> Repository:
    """构建指向内存 SQLite 的全新 Repository（含建表）。"""
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    return Repository(session)


@pytest.mark.property
@settings(max_examples=100)
@given(
    role=st.sampled_from(_ROLES),
    account=_account_strategy,
    password=_password_strategy,
    now=_now_strategy,
)
def test_login_token_role_matches_user_role(
    role: str, account: str, password: str, now: datetime
) -> None:
    """登录成功后，令牌的 role 声明与登录结果的 role 均等于用户实际角色。

    **Validates: Requirements 1.3**
    """
    repo = _fresh_repository()

    # 以采样角色与正确凭据创建用户并提交。
    repo.create_user(role=role, account=account, email="user@example.com", password=password)
    repo.commit()

    # 使用正确凭据登录。
    result = AuthService(repo).login(account, password, now)

    # 1) 登录成功并签发了令牌。
    assert result.ok is True
    assert result.token is not None

    # 2) 登录结果中的 role 等于用户实际角色。
    assert result.role == role

    # 3a) 直接解码令牌（关闭 exp 校验）：role 声明等于用户实际角色。
    claims = jwt.decode(
        result.token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"verify_exp": False},
    )
    assert claims["role"] == role

    # 3b) 经 verify_token 解析：返回的 role 同样等于用户实际角色。
    token_result = AuthService(repo).verify_token(result.token, now)
    assert token_result.ok is True
    assert token_result.role == role
