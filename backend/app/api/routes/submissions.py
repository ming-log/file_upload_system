"""作业提交路由（需求 9、10、11）。

* ``GET /submissions`` —— 列出提交记录（教师/管理员查看全部，学生仅见自己）。
* ``POST /assignments/{assignment_id}/submissions`` —— 学生上传作业文件（支持多文件 + 备注）。
  同一学生对同一作业重复提交将覆盖既有记录。
* ``GET /submissions/{submission_id}/files/{storage_id}`` —— 下载某个提交文件。
* ``GET /courses/{course_id}/submissions/export`` —— 教师一键下载某课程全部提交文件
  与学生提交状态表（打包为 ZIP）。

文件保存到存储服务（默认 MinIO，按课程/作业/学生分层组织）。每个文件的扩展名与
大小依据作业约束校验；``*`` 表示允许任意类型。提交成功后异步发起邮件通知（失败不
影响提交结果）。
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.adapters.email_service import EmailService, SubmissionRecord
from app.adapters.storage_service import StorageService
from app.api.deps import (
    CurrentUser,
    get_email_service,
    get_repository,
    get_storage_service,
    require_roles,
    to_naive_cn,
    now_provider,
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
        me = repository.get_user(current.user_id)
        if me is not None:
            subs = [s for s in subs if s.student_id == me.id]
    return [serialize_submission(s) for s in subs]


@router.post("/assignments/{assignment_id}/submissions", summary="学生提交作业文件")
async def submit_assignment(
    assignment_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="作业文件（可多个）"),
    comment: str = Form(default=""),
    current: CurrentUser = Depends(require_roles("student")),
    repository: Repository = Depends(get_repository),
    storage: StorageService = Depends(get_storage_service),
    email_service: EmailService = Depends(get_email_service),
    now: datetime = Depends(now_provider),
) -> dict[str, Any]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise http_exception_for(ErrorCode.ASSIGNMENT_NOT_FOUND)

    student = repository.get_user(current.user_id)
    if student is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)

    submitted_at = to_naive_cn(now)
    if submitted_at > assignment.deadline:
        raise http_exception_for(ErrorCode.DEADLINE_PASSED)

    if not files:
        raise http_exception_for(ErrorCode.EMPTY_FILE)

    allowed = list(assignment.allowed_extensions)
    max_bytes = assignment.max_file_size_mb * 1024 * 1024
    saved_files: list[dict[str, Any]] = []

    # 构造分层对象键前缀：课程/作业/学号_姓名，使文件在对象存储中按层级组织。
    course = repository.get_course(assignment.course_id)
    course_label = f"{course.name}" if course is not None else assignment.course_id
    student_label = student.student_id or student.account
    if student.name:
        student_label = f"{student_label}_{student.name}"
    storage_prefix = f"{course_label}/{assignment.title}/{student_label}"

    for upload in files:
        content = await upload.read()
        filename = upload.filename or "file"
        if len(content) <= 0:
            raise http_exception_for(ErrorCode.EMPTY_FILE)
        if not _ext_allowed(filename, allowed):
            raise http_exception_for(ErrorCode.EXTENSION_NOT_ALLOWED)
        if len(content) > max_bytes:
            raise http_exception_for(ErrorCode.FILE_TOO_LARGE)
        result = storage.save(filename, content, prefix=storage_prefix)
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

    # 异步邮件通知（失败不影响提交结果）。提交成功或修改作业后，主动给学生邮箱发送通知。
    # 使用 FastAPI BackgroundTasks 在响应返回后可靠执行，避免裸 create_task 被回收。
    record = SubmissionRecord(
        submission_id=payload["id"],
        assignment_title=assignment.title,
        submitted_at=submitted_at,
        file_name=", ".join(f["name"] for f in saved_files),
    )
    background_tasks.add_task(
        email_service.notify_submission, record, student.email
    )

    return payload


@router.get(
    "/submissions/{submission_id}/file",
    summary="下载提交文件",
)
def download_submission_file(
    submission_id: str,
    storageId: str,
    current: CurrentUser = Depends(require_roles("admin", "teacher", "student")),
    repository: Repository = Depends(get_repository),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    """下载某个提交文件。

    ``storageId`` 以**查询参数**传入（其值为含 ``/`` 的分层对象键，作为路径段会被
    路由切断导致 404，故改用查询参数）。学生仅能下载自己的提交文件；教师/管理员
    可下载任意提交文件。
    """
    submission = repository.get_submission(submission_id)
    if submission is None:
        raise http_exception_for(ErrorCode.ASSIGNMENT_NOT_FOUND, message="提交记录不存在")

    # 学生仅能下载自己的提交。
    if current.role == "student":
        me = repository.get_user(current.user_id)
        if me is None or submission.student_id != me.id:
            raise http_exception_for(ErrorCode.FORBIDDEN)

    meta = next((f for f in (submission.files or []) if f.get("storageId") == storageId), None)
    if meta is None:
        raise http_exception_for(ErrorCode.STORAGE_FAILED, message="文件不可用")

    loader = getattr(storage, "load", None)
    if not callable(loader):
        raise http_exception_for(ErrorCode.STORAGE_FAILED, message="文件不可用")

    data = loader(storageId)
    if data is None:
        raise http_exception_for(ErrorCode.STORAGE_FAILED, message="文件不存在")

    filename = meta.get("name", "download")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


def _safe_path_segment(text: str) -> str:
    """清洗用于 ZIP 内路径的一段名称（去除分隔符与危险字符）。"""
    seg = (text or "").strip().replace("/", "_").replace("\\", "_")
    for bad in ('\0', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t'):
        seg = seg.replace(bad, "_")
    seg = seg.strip(". ")
    return seg or "_"


def _content_disposition(filename: str) -> str:
    """构造支持 UTF-8 文件名（含中文）的 Content-Disposition 头。"""
    from urllib.parse import quote

    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "download"
    quoted = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"


@router.get(
    "/courses/{course_id}/submissions/export",
    summary="导出课程全部提交（ZIP：文件 + 提交状态表）",
)
def export_course_submissions(
    course_id: str,
    _user: CurrentUser = Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
    storage: StorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """打包下载某课程下全部作业的提交文件，并附带学生提交状态表（CSV）。

    ZIP 结构::

        <课程名>/
          提交状态表.csv
          <作业标题>/
            <学号_姓名>/
              <文件1>
              <文件2>
        ...

    提交状态表包含每个作业 × 班级每名学生的提交状态（已提交/迟交/未提交）、提交
    时间、文件名与备注，便于教师一览全班提交情况。
    """
    course = repository.get_course(course_id)
    if course is None:
        raise http_exception_for(ErrorCode.COURSE_NOT_FOUND)

    # 该课程下的作业、班级学生、提交记录。
    assignments = [a for a in repository.list_assignments() if a.course_id == course_id]
    students = repository.list_students(class_id=course.class_id)
    students_by_id = {s.id: s for s in students}
    all_submissions = repository.list_submissions()
    assignment_ids = {a.id for a in assignments}
    submissions = [s for s in all_submissions if s.assignment_id in assignment_ids]
    # (assignment_id, student_id) -> submission，便于状态表查表。
    sub_index = {(s.assignment_id, s.student_id): s for s in submissions}

    loader = getattr(storage, "load", None)

    course_folder = _safe_path_segment(course.name)
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) 提交状态表（CSV，带 BOM 以便 Excel 正确识别中文）。
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(
            ["作业标题", "学号", "姓名", "提交状态", "提交时间", "是否迟交", "文件", "备注"]
        )
        for assignment in assignments:
            deadline = assignment.deadline
            for student in students:
                sub = sub_index.get((assignment.id, student.id))
                if sub is None:
                    writer.writerow(
                        [assignment.title, student.student_id or student.account,
                         student.name or "", "未提交", "", "", "", ""]
                    )
                    continue
                submitted_at = sub.submitted_at
                is_late = submitted_at is not None and deadline is not None and submitted_at > deadline
                file_names = "; ".join(f.get("name", "") for f in (sub.files or []))
                writer.writerow(
                    [
                        assignment.title,
                        student.student_id or student.account,
                        student.name or "",
                        "已提交",
                        submitted_at.strftime("%Y-%m-%d %H:%M:%S") if submitted_at else "",
                        "是" if is_late else "否",
                        file_names,
                        sub.comment or "",
                    ]
                )
        csv_bytes = "\ufeff".encode("utf-8") + csv_buf.getvalue().encode("utf-8")
        zf.writestr(f"{course_folder}/提交状态表.csv", csv_bytes)

        # 2) 提交文件，按 作业标题/学号_姓名/文件名 组织。
        if callable(loader):
            for assignment in assignments:
                a_folder = _safe_path_segment(assignment.title)
                for sub in submissions:
                    if sub.assignment_id != assignment.id:
                        continue
                    student = students_by_id.get(sub.student_id)
                    if student is not None:
                        label = student.student_id or student.account
                        if student.name:
                            label = f"{label}_{student.name}"
                    else:
                        label = sub.student_id
                    s_folder = _safe_path_segment(label)
                    seen_names: dict[str, int] = {}
                    for f in sub.files or []:
                        storage_id = f.get("storageId")
                        if not storage_id:
                            continue
                        data = loader(storage_id)
                        if data is None:
                            continue
                        name = _safe_path_segment(f.get("name", "file"))
                        # 同一学生多文件重名时追加序号避免覆盖。
                        if name in seen_names:
                            seen_names[name] += 1
                            stem, ext = os.path.splitext(name)
                            name = f"{stem}({seen_names[name]}){ext}"
                        else:
                            seen_names[name] = 0
                        zf.writestr(
                            f"{course_folder}/{a_folder}/{s_folder}/{name}", data
                        )

    buffer.seek(0)
    zip_name = f"{course.name}_提交汇总.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition(zip_name)},
    )


@router.get(
    "/assignments/{assignment_id}/submissions/export",
    summary="导出某作业全部提交（ZIP：文件 + 提交状态表）",
)
def export_assignment_submissions(
    assignment_id: str,
    _user: CurrentUser = Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
    storage: StorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """打包下载某个作业的全部提交文件，并附带该作业的学生提交状态表（CSV）。

    ZIP 结构::

        <作业标题>/
          提交状态表.csv
          <学号_姓名>/
            <文件1>
            <文件2>
        ...

    提交状态表覆盖该作业所属班级的每名学生（含未提交），便于教师一览本次作业的
    提交情况。
    """
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise http_exception_for(ErrorCode.ASSIGNMENT_NOT_FOUND)

    course = repository.get_course(assignment.course_id)
    class_id = course.class_id if course is not None else None
    students = repository.list_students(class_id=class_id) if class_id else []
    students_by_id = {s.id: s for s in students}
    submissions = [
        s for s in repository.list_submissions() if s.assignment_id == assignment_id
    ]
    sub_by_student = {s.student_id: s for s in submissions}

    loader = getattr(storage, "load", None)

    a_folder = _safe_path_segment(assignment.title)
    deadline = assignment.deadline
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) 提交状态表（CSV，带 BOM 以便 Excel 正确识别中文）。
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(
            ["学号", "姓名", "提交状态", "提交时间", "是否迟交", "文件", "备注"]
        )
        roster = students if students else [students_by_id.get(s.student_id) for s in submissions]
        for student in roster:
            if student is None:
                continue
            sub = sub_by_student.get(student.id)
            if sub is None:
                writer.writerow(
                    [student.student_id or student.account, student.name or "",
                     "未提交", "", "", "", ""]
                )
                continue
            submitted_at = sub.submitted_at
            is_late = submitted_at is not None and deadline is not None and submitted_at > deadline
            file_names = "; ".join(f.get("name", "") for f in (sub.files or []))
            writer.writerow(
                [
                    student.student_id or student.account,
                    student.name or "",
                    "已提交",
                    submitted_at.strftime("%Y-%m-%d %H:%M:%S") if submitted_at else "",
                    "是" if is_late else "否",
                    file_names,
                    sub.comment or "",
                ]
            )
        csv_bytes = "\ufeff".encode("utf-8") + csv_buf.getvalue().encode("utf-8")
        zf.writestr(f"{a_folder}/提交状态表.csv", csv_bytes)

        # 2) 提交文件，按 学号_姓名/文件名 组织。
        if callable(loader):
            for sub in submissions:
                student = students_by_id.get(sub.student_id)
                if student is not None:
                    label = student.student_id or student.account
                    if student.name:
                        label = f"{label}_{student.name}"
                else:
                    label = sub.student_id
                s_folder = _safe_path_segment(label)
                seen_names: dict[str, int] = {}
                for f in sub.files or []:
                    storage_id = f.get("storageId")
                    if not storage_id:
                        continue
                    data = loader(storage_id)
                    if data is None:
                        continue
                    name = _safe_path_segment(f.get("name", "file"))
                    if name in seen_names:
                        seen_names[name] += 1
                        stem, ext = os.path.splitext(name)
                        name = f"{stem}({seen_names[name]}){ext}"
                    else:
                        seen_names[name] = 0
                    zf.writestr(f"{a_folder}/{s_folder}/{name}", data)

    buffer.seek(0)
    zip_name = f"{assignment.title}_提交汇总.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition(zip_name)},
    )
