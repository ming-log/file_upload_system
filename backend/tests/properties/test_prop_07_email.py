# Feature: homework-upload-system, Property 7: 邮箱格式校验
"""Property 7：邮箱格式校验。

依据 design.md「Correctness Properties」Property 7：

    *For any* 字符串 ``email``，``validate_email(email)`` 通过当且仅当其满足：
    恰好包含一个 ``@``、``@`` 前本地名非空、``@`` 后域名非空且至少包含一个点号；
    创建用户时不合法邮箱返回“邮箱格式错误”（:attr:`ErrorCode.INVALID_EMAIL_FORMAT`）。

**Validates: Requirements 2.5**

测试策略：在测试内独立编码 spec 谓词
``email.count("@") == 1 and local != "" and domain != "" and "." in domain``，
并断言 ``validate_email(email).ok`` 与该谓词一致；不通过时断言错误码为
``INVALID_EMAIL_FORMAT``。输入同时覆盖“构造合法邮箱”（local + '@' + 带点域名）
与 Hypothesis ``text()`` 生成的任意/无效字符串。
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from app.core.errors import ErrorCode
from app.core.validators import validate_email


def _spec_predicate(email: str) -> bool:
    """独立编码的 Property 7 规格谓词（不依赖被测实现）。

    通过当且仅当：恰好一个 ``@``、本地名非空、域名非空且域名含至少一个点号。
    """
    if email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    return local != "" and domain != "" and "." in domain


# “本地名”片段：允许为空，以便覆盖本地名为空的不合法情形。
_local_fragments = st.text(
    alphabet=st.characters(blacklist_characters="@"),
    max_size=8,
)

# “域名标签”片段：不含 '@' 与 '.'，用于通过 '.' 拼接出带点的合法域名。
_domain_labels = st.text(
    alphabet=st.characters(blacklist_characters="@."),
    min_size=1,
    max_size=6,
)


@st.composite
def _valid_emails(draw: st.DrawFn) -> str:
    """构造一定满足规格谓词的合法邮箱：local + '@' + 至少含一个点号的域名。"""
    local = draw(st.text(alphabet=st.characters(blacklist_characters="@"), min_size=1, max_size=8))
    labels = draw(st.lists(_domain_labels, min_size=2, max_size=4))
    domain = ".".join(labels)
    return f"{local}@{domain}"


# 混合输入空间：任意字符串、由片段拼出的候选、以及一定合法的邮箱。
_emails = st.one_of(
    st.text(max_size=20),
    st.builds(lambda l, d: f"{l}@{d}", _local_fragments, st.text(max_size=10)),
    _valid_emails(),
)


@pytest.mark.property
@settings(max_examples=100)
@given(email=_emails)
def test_validate_email_matches_spec_predicate(email: str) -> None:
    """validate_email(email).ok 当且仅当独立规格谓词成立；失败码为 INVALID_EMAIL_FORMAT。"""
    expected = _spec_predicate(email)
    result = validate_email(email)

    assert result.ok is expected, (
        f"validate_email({email!r}).ok={result.ok} 与规格谓词 {expected} 不一致"
    )

    if result.ok:
        assert result.error_code is None
    else:
        assert result.error_code == ErrorCode.INVALID_EMAIL_FORMAT
