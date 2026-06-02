# Feature: homework-upload-system, Property 33: 邮件正文包含必备信息
"""Property 33：邮件正文包含必备信息（design.md「Correctness Properties」）。

*For any* 作业标题 ``assignment_title``、提交时间 ``submitted_at`` 与提交文件名
``file_name``，纯函数 :func:`app.adapters.email_service.build_email_body` 返回的
邮件正文必定同时包含以下三项信息（需求 11.2）：

* 作业标题 ``assignment_title``（原样嵌入）；
* 提交时间，按 :data:`app.adapters.email_service.EMAIL_TIME_FORMAT`
  （``%Y-%m-%d %H:%M:%S`` → ``YYYY-MM-DD HH:MM:SS``，精确到秒）格式化后的字符串；
* 提交文件名 ``file_name``（原样嵌入）。

使用 Hypothesis 的 ``text()`` 生成标题与文件名（覆盖广泛字符），``datetimes()``
生成提交时间；以 Python ``in`` 子串检查断言三项信息均存在于正文中。

**Validates: Requirements 11.2**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.adapters.email_service import EMAIL_TIME_FORMAT, build_email_body


@pytest.mark.property
@settings(max_examples=100)
@given(
    assignment_title=st.text(min_size=1, max_size=50),
    submitted_at=st.datetimes(),
    file_name=st.text(min_size=1, max_size=50),
)
def test_email_body_contains_required_info(
    assignment_title: str, submitted_at, file_name: str
) -> None:
    """邮件正文同时包含作业标题、秒精度提交时间与提交文件名。"""
    body = build_email_body(assignment_title, submitted_at, file_name)

    # 作业标题原样出现在正文中。
    assert assignment_title in body
    # 提交时间按 EMAIL_TIME_FORMAT 格式化（精确到秒）后出现在正文中。
    assert submitted_at.strftime(EMAIL_TIME_FORMAT) in body
    # 提交文件名原样出现在正文中。
    assert file_name in body
