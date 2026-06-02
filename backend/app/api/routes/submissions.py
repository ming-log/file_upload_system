"""作业提交路由（需求 9、10、11）。

* ``GET /submissions`` —— 列出提交记录（教师/管理员查看全部，学生仅见自己）。
* ``POST /assignments/{assignment_id}/submissions`` —— 学生上传作业文件（支持多文件 + 备注）。
  同一学生对同一作业重复提交将覆盖既有记录。
* ``GET /submissions/{submission_id}/files/{storage_id}`` —— 下载某个提交文件。

文件保存到存储服务（默认本地磁盘）。每个文件的扩展名与大小依据作业约束校验；
``*`` 表示允许任意类型。提交成功后异步发起邮件通知（失败不影响提交结果）。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.adapters.email_service import EmailService, SubmissionRecord
from app.adapters.storage_service import LocalDiskStorageService, StorageService
from app.api.deps import (
    CurrentUser,
    get_email_service,
    get_repository,
    get_storage_service,
    require_roles,
    to_naive_utc,
    utcnow,
)
from app.api.errors import http_exception_for
from app.api.serializers import serialize_submission
from app.core.errors import ErrorCode
from app.repository import Repository

__all__ = ["router"]

router = APIRouter(tags=["submissions"])


def _ext_allowed(filename: str, allowed: list[str]) -> bool:
    if "*" in allowed:
        return True
    _, ext = os.path.splitext(filename)
    return ext.lower() in {a.lower() for a in allowed}


@router.get("/submissions", summary="提交记录列表")
def list_submissions(
    current: CurrentUser = Depends(require_roles("admin", "teacher", "student")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    subs = repository.list_submissions()
    if current.role == "student":
        me = repository.get_user_by_account(current.account)
        if me is not None:
            subs = [s for s in subs if s.student_id == me.id]
    return [serialize_submission(s) for s in subs]


@router.post("/assignments/{assignment_id}/submissions", summary="学生提交作业文件")
async def submit_assignment(
    assignment_id: str,
    files: list[UploadFile] = File(..., description="作业文件（可多个）"),
    comment: str = Form(default=""),
    current: CurrentUser = Depends(require_roles("student")),
    repository: Repository = Depends(get_repository),
    storage: StorageService = Depends(get_storage_service),
    email_service: EmailService = Depends(get_email_service),
    now: datetime = Depends(utcnow),
) -> dict[str, Any]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise http_exception_for(ErrorCode.ASSIGNMENT_NOT_FOUND)

    student = repository.get_user_by_account(current.account)
    if student is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)

    submitted_at = to_naive_utc(now)
    if submitted_at > assignment.deadline:
        raise http_exception_for(ErrorCode.DEADLINE_PASSED)

    if not files:
        raise http_exception_for(ErrorCode.EMPTY_FILE)

    allowed = list(assignment.allowed_extensions)
    max_bytes = assignment.max_file_size_mb * 1024 * 1024
    saved_files: list[dict[str, Any]] = []

    for upload in files:
        content = await upload.read()
        filename = upload.filename or "file"
        if len(content) <= 0:
            raise http_exception_for(ErrorCode.EMPTY_FILE)
        if not _ext_allowed(filename, allowed):
            raise http_exception_for(ErrorCode.EXTENSION_NOT_ALLOWED)
        if len(content) > max_bytes:
            raise http_exception_for(ErrorCode.FILE_TOO_LARGE)
        result = storage.save(filename, content)
        if not result.ok:
            assert result.error_code is not None
            raise http_exception_for(result.error_code)
        _, ext = os.path.splitext(filename)
        saved_files.append(
            {
                "name": filename,
                "size": len(content),
                "type": ext.lower(),
                "storageId": result.storage_id,
            }
        )

    with repository.transaction():
        submission = repository.upsert_submission(
            student_id=student.id,
            assignment_id=assignment_id,
            files=saved_files,
            comment=comment,
            submitted_at=submitted_at,
        )
        payload = serialize_submission(submission)

    # 异步邮件通知（失败不影响提交结果）。
    try:
        record = SubmissionRecord(
            submission_id=payload["id"],
            assignment_title=assignment.title,
            submitted_at=submitted_at,
            file_name=", ".join(f["name"] for f in saved_files),
        )
        import asyncio

        asyncio.create_task(email_service.notify_submission(record, student.email))
    except Exception:  # noqa: BLE001 - 邮件失败绝不影响提交
        pass

    return payload


@router.get(
    "/submissions/{submission_id}/files/{storage_id}",
    summary="下载提交文件",
)
def download_submission_file(
    submission_id: str,
    storage_id: str,
    _user=Depends(require_roles("admin", "teacher", "student")),
    repository: Repository = Depends(get_repository),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    submission = repository.get_submission(submission_id)
    if submission is None:
        raise http_exception_for(ErrorCode.ASSIGNMENT_NOT_FOUND, message="提交记录不存在")

    meta = next((f for f in (submission.files or []) if f.get("storageId") == storage_id), None)
    if meta is None or not isinstance(storage, LocalDiskStorageService):
        raise http_exception_for(ErrorCode.STORAGE_FAILED, message="文件不可用")

    data = storage.load(storage_id)
    if data is None:
        raise http_exception_for(ErrorCode.STORAGE_FAILED, message="文件不存在")

    filename = meta.get("name", "download")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
