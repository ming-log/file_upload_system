# Feature: homework-upload-system, Property 30: 成功提交不变量
"""Property 30：成功提交不变量。

依据 design.md「Correctness Properties」Property 30：

    *For any* 通过角色、非空、扩展名、大小与截止时间校验且存储成功的提交，系统应
    调用一次存储保存、创建一条提交记录，且该记录正确包含提交学生、关联作业与提交
    时间。

**Validates: Requirements 9.7, 9.8, 9.9**

测试策略：

构造一条「必定通过全部前置校验且存储成功」的提交，断言成功路径下的不变量同时成立：

1. **角色**：以 ``"Student"`` 身份提交（通过角色门控，需求 9.1 / 9.2）。
2. **作业存在性**：使用真实创建并提交的 ``Assignment`` 的标识（通过存在性校验，
   需求 9.1）。
3. **非空文件**：``content`` 生成为至少 1 字节（通过空文件校验，需求 9.3）。
4. **扩展名**：作业允许集合固定为 ``["pdf"]``，文件名固定形如 ``f"{base}.pdf"``，
   故扩展名（不区分大小写）必然被允许（需求 9.4）。
5. **文件大小**：作业 ``max_file_size_mb=5``（= 5 MiB），``content`` 长度被限制在
   远小于该上限的范围内，故大小校验必然通过（需求 9.5）。
6. **截止时间**：固定 ``now = 2024-01-01 12:00:00``，作业 ``deadline = now + 1 天``，
   即提交按时（``now <= deadline``，通过截止时间校验，需求 9.6）。
7. **存储成功**：注入处于成功模式的 :class:`FakeStorageService`，
   :meth:`StorageService.save` 必然返回唯一 ``storage_id``。

在以上条件下，断言成功提交不变量：

* ``result.ok is True`` 且 ``result.submission_id`` 非 ``None``（需求 9.7）。
* ``storage.save_call_count == 1``——存储保存恰好被调用一次（需求 9.7）。
* 数据库中恰好存在一条 :class:`~app.models.Submission` 记录（需求 9.8）。
* 该记录正确包含提交学生（``student_id == 学生 User.id``）、关联作业
  （``assignment_id == 作业 id``）与提交时间（``submitted_at == now``），并正确
  记录文件名与非空 ``storage_id``（且该 ``storage_id`` 即存储返回的标识，需求 9.9）。

为保证 Hypothesis 各用例之间 DB 状态互相隔离，测试体内部每次都构造一套全新的内存
引擎 + 会话 + 仓储（``create_db_engine`` -> ``create_all`` ->
``create_session_factory`` -> ``Repository(session)``）。``email_service`` 不注入
（``None``），从而跳过邮件触发，将断言聚焦在提交记录与存储调用的不变量上。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from app.adapters.storage_service import FakeStorageService
from app.db import create_all, create_db_engine, create_session_factory
from app.models import Submission
from app.repository import Repository
from app.services.submission_service import SubmissionService, UploadedFile

# 固定的“当前时间”，使截止时间判定与提交时间断言具有确定性（与真实时钟无关）。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 作业配置（与被测属性无关，固定为合法值，使前置校验必然通过）。
_ALLOWED_EXTENSIONS = ["pdf"]
_MAX_FILE_SIZE_MB = 5

# 教师账号：固定且足够长（>20 字符），保证与生成的学生账号（最长 20）绝不重合，
# 避免 users.account 唯一约束冲突——该约束与 Property 30 无关，属测试夹具范畴。
_TEACHER_ACCOUNT = "teacher-fixture-account-0123456789"

# 学生账号 / 学号：非空白可见 ASCII（码点 33..126），长度 1..20。
_non_blank_text = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=20,
)

# 文件名基名：仅由字母/数字构成（不含 '.'、路径分隔符等），保证 ``f"{base}.pdf"``
# 必然被 os.path.splitext 识别出 ``.pdf`` 扩展名，从而满足 Property 30 的前置条件
# （提交通过扩展名校验）。基名取值空间与被测属性无关，属测试夹具范畴。
_filename_base = st.text(
    alphabet=st.characters(
        min_codepoint=ord("0"),
        max_codepoint=ord("z"),
        whitelist_categories=("Lu", "Ll", "Nd"),
    ),
    min_size=1,
    max_size=20,
)

# 文件内容：至少 1 字节（通过空文件校验），且远小于 5 MiB 上限（通过大小校验）。
_file_content = st.binary(min_size=1, max_size=64)


@pytest.mark.property
@settings(max_examples=100)
@given(
    base=_filename_base,
    content=_file_content,
    student_account=_non_blank_text,
    student_id=_non_blank_text,
)
def test_successful_submission_invariant(
    base: str,
    content: bytes,
    student_account: str,
    student_id: str,
) -> None:
    """通过全部前置校验且存储成功的提交：恰一次存储保存 + 恰一条正确的提交记录。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 构造完整关联链：Teacher -> Class -> Course -> Assignment，以及提交学生 Student。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account=_TEACHER_ACCOUNT)
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            course = repo.create_course(
                semester="2024-Spring", name="Course", class_id=clazz.id
            )
            assignment = repo.create_assignment(
                title="HW",
                course_id=course.id,
                allowed_extensions=_ALLOWED_EXTENSIONS,
                max_file_size_mb=_MAX_FILE_SIZE_MB,
                # 截止时间晚于 now（提交按时），通过截止时间校验（需求 9.6）。
                deadline=_NOW + timedelta(days=1),
            )
            student = repo.create_user(
                role="Student",
                account=student_account,
                student_id=student_id,
                class_id=clazz.id,
            )
            assignment_id = assignment.id
            student_pk = student.id

        # 文件名扩展名为 pdf（在允许集合内）、内容非空且远小于大小上限。
        file = UploadedFile(filename=f"{base}.pdf", content=content)

        # 注入成功模式的 FakeStorageService；不注入 email_service（跳过邮件触发）。
        storage = FakeStorageService()
        service = SubmissionService(repo, storage)

        result = service.submit("Student", student_account, assignment_id, file, _NOW)

        # 需求 9.7：提交成功并返回提交记录标识。
        assert result.ok is True, f"提交应成功，实际 error_code={result.error_code}"
        assert result.error_code is None
        assert result.submission_id is not None

        # 需求 9.7：存储保存恰好被调用一次（成功路径下不重试、不重复保存）。
        assert storage.save_call_count == 1, (
            f"存储保存应恰好调用一次，实际 {storage.save_call_count} 次"
        )
        # 成功保存后，存储中恰好存在一个对象（其键即返回的唯一 storage_id）。
        assert len(storage.objects) == 1

        # 需求 9.8：数据库中恰好存在一条提交记录。
        submission_count = repo.session.scalar(
            select(func.count()).select_from(Submission)
        )
        assert submission_count == 1, (
            f"应恰好创建一条提交记录，实际 {submission_count} 条"
        )

        # 需求 9.9：该记录正确包含提交学生、关联作业、提交时间、文件名与 storage_id。
        submission = repo.session.scalar(select(Submission))
        assert submission is not None
        assert submission.id == result.submission_id
        assert submission.student_id == student_pk  # 提交学生（User.id 外键）
        assert submission.assignment_id == assignment_id  # 关联作业
        assert submission.submitted_at == _NOW  # 提交时间
        assert submission.file_name == file.filename  # 文件名
        # storage_id 非空，且与存储服务返回的唯一标识一致（存在于存储对象映射中）。
        assert submission.storage_id
        assert submission.storage_id in storage.objects
    finally:
        session.close()
        engine.dispose()
