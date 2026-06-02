# Feature: homework-upload-system, Property 6: 角色取值校验
"""Property 6: 角色取值校验。

依据 design.md「Correctness Properties」Property 6：

    *For any* 字符串 ``role``，``validate_role(role)`` 通过当且仅当
    ``role ∈ {Admin, Teacher, Student}``；创建用户时非法角色返回
    “角色取值无效”（:attr:`ErrorCode.INVALID_ROLE`）。

**Validates: Requirements 2.2, 2.7**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ErrorCode
from app.core.validators import VALID_ROLES, validate_role

# 合法角色集合（与 validators.VALID_ROLES 保持一致），供采样生成器使用。
_VALID_ROLE_LIST = ["Admin", "Teacher", "Student"]

# 任意字符串：以 text() 覆盖广阔输入空间（含空串、空白、随机文本），
# 再混入采样的合法角色，确保两类输入都被充分探索。
_role_strategy = st.one_of(
    st.text(),
    st.sampled_from(_VALID_ROLE_LIST),
)


@pytest.mark.property
@settings(max_examples=100)
@given(role=_role_strategy)
def test_validate_role_ok_iff_in_valid_roles(role: str) -> None:
    """validate_role(role).ok 为真，当且仅当 role 属于合法角色集合。"""
    result = validate_role(role)
    expected_ok = role in {"Admin", "Teacher", "Student"}

    assert result.ok is expected_ok

    if expected_ok:
        # 通过时不应携带错误码。
        assert result.error_code is None
    else:
        # 失败时必须携带 INVALID_ROLE。
        assert result.error_code is ErrorCode.INVALID_ROLE


@pytest.mark.property
@settings(max_examples=100)
@given(role=st.sampled_from(_VALID_ROLE_LIST))
def test_valid_roles_always_pass(role: str) -> None:
    """所有合法角色恒通过校验，且常量集合与字面集合一致。"""
    assert validate_role(role).ok is True
    assert set(VALID_ROLES) == {"Admin", "Teacher", "Student"}
