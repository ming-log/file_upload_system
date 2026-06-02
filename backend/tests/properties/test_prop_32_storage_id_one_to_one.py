# Feature: homework-upload-system, Property 32: 存储标识与提交记录一一对应
"""Property 32：存储标识与提交记录一一对应（design.md「Correctness Properties」）。

*For any* 一组成功创建的提交记录，其 ``storage_id`` 互不重复，且每个 ``storage_id``
恰好关联一条提交记录。

**Validates: Requirements 10.4**

被测对象：:meth:`app.services.submission_service.SubmissionService.submit` 与其依赖
的 :class:`app.adapters.storage_service.FakeStorageService`。后者在成功模式下每次
:meth:`save` 都返回一个**互不相同**的 ``storage_id``（由 uuid4 派生），从而模拟
MinIO「保存成功返回系统内唯一存储标识」的语义（需求 10.1 / 10.4）。

测试策略 / 可测试性（每个用例构造全新内存引擎 + Repository，保证用例间隔离）：

* 先创建一条完整的关联链：Teacher、Class、Course、Assignment（允许扩展名
  ``["pdf"]``、最大 5MB、截止时间为 ``now + 1 天``）、Student，并提交。``now``
  固定为确定值，使截止时间校验与时钟无关。
* 生成提交数量 ``n``（1..10），循环 ``n`` 次调用
  ``service.submit("Student", student_account, assignment_id, UploadedFile(...), now)``。
  每次提交都会经由 :class:`FakeStorageService`（成功模式）获得一个唯一 ``storage_id``。

断言：

1. 全部 ``n`` 次提交均成功（``result.ok is True``）。
2. 数据库中恰好存在 ``n`` 条 :class:`Submission` 记录。
3. 这些记录的 ``storage_id`` 两两不同（``len(set(...)) == n``）。
4. 存在一一映射：不存在某个 ``storage_id`` 关联超过一条提交记录（按
   ``storage_id`` 分组后每组计数恒为 1）。
5. 各次提交返回的 ``submission_id`` 也互不相同。
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

# 固定的“当前时间”，使截止时间校验具有确定性（与真实时钟无关）。
_NOW = datetime(2024, 1, 1, 12, 0, 0)

# 提交学生账号（在 setup 阶段创建对应的 Student 用户）。
_STUDENT_ACCOUNT = "student-acct"


@pytest.mark.property
@settings(max_examples=100)
@given(n=st.integers(min_value=1, max_value=10))
def test_storage_id_one_to_one_with_submissions(n: int) -> None:
    """n 次成功提交后：storage_id 两两不同，且每个 storage_id 恰好关联一条提交记录。"""
    # 每个用例使用全新的内存数据库，保证用例间状态隔离。
    engine = create_db_engine()
    create_all(engine)
    session = create_session_factory(engine)()
    try:
        repo = Repository(session)

        # 1) 构造完整关联链：Teacher -> Class -> Course -> Assignment + Student。
        with repo.transaction():
            teacher = repo.create_user(role="Teacher", account="teacher-acct")
            clazz = repo.create_class(
                school="S", grade="G", major="M", teacher_id=teacher.id
            )
            course = repo.create_course(
                semester="2024-Spring", name="Course", class_id=clazz.id
            )
            assignment = repo.create_assignment(
                title="HW",
                course_id=course.id,
                allowed_extensions=["pdf"],
                max_file_size_mb=5,
                deadline=_NOW + timedelta(days=1),  # 截止时间晚于 now，允许提交
            )
            repo.create_user(
                role="Student",
                account=_STUDENT_ACCOUNT,
                student_id="stu-1",
                class_id=clazz.id,
            )
            assignment_id = assignment.id

        # 成功模式的存储 fake：每次 save 返回一个唯一 storage_id（需求 10.4）。
        service = SubmissionService(repo, FakeStorageService())

        # 2) 连续提交 n 次，收集各次返回的 submission_id。
        submission_ids: list[str] = []
        for i in range(n):
            result = service.submit(
                "Student",
                _STUDENT_ACCOUNT,
                assignment_id,
                UploadedFile(filename=f"f{i}.pdf", content=b"data"),
                _NOW,
            )
            # 断言 1：每次提交都成功。
            assert result.ok is True, f"第 {i} 次提交应成功，实际 error={result.error_code}"
            assert result.submission_id is not None
            submission_ids.append(result.submission_id)

        # 3) 数据库中恰好存在 n 条提交记录（断言 2）。
        total = repo.session.scalar(select(func.count()).select_from(Submission))
        assert total == n, f"应有 {n} 条提交记录，实际 {total} 条"

        # 4) 取出全部 storage_id，断言两两不同（断言 3）。
        storage_ids = list(repo.session.scalars(select(Submission.storage_id)).all())
        assert len(storage_ids) == n
        assert len(set(storage_ids)) == n, "所有提交记录的 storage_id 应互不重复"

        # 5) 一一映射：按 storage_id 分组，任何分组的计数都不得超过 1（断言 4）。
        grouped = repo.session.execute(
            select(Submission.storage_id, func.count())
            .group_by(Submission.storage_id)
        ).all()
        assert len(grouped) == n
        assert all(count == 1 for _sid, count in grouped), (
            "每个 storage_id 应恰好关联一条提交记录（不存在一对多）"
        )

        # 6) 各次返回的 submission_id 也互不相同。
        assert len(set(submission_ids)) == n, "各次提交的 submission_id 应互不相同"
    finally:
        session.close()
        engine.dispose()
