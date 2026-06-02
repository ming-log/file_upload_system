"""作业路由（需求 8、9）。

* ``GET /assignments`` —— 列出全部作业（前端按课程归属过滤）。
* ``POST /assignments`` —— 教师创建作业。
* ``PUT /assignments/{assignment_id}`` —— 更新作业。
* ``DELETE /assignments/{assignment_id}`` —— 删除作业（级联提交）。

``allowedFileTypes`` 直接存储前端的文件类型 token（如 ``.pdf`` / ``*``）；
``deadline`` 由前端以 ISO-8601 / ``datetime-local`` 字符串提交。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_repository, require_roles, to_naive_utc
from app.api.errors import http_exception_for
from app.api.serializers import serialize_assignment
from app.core.errors import ErrorCode
from app.core.validators import validate_required
from app.repository import Repository

__all__ = ["router"]

router = APIRouter(prefix="/assignments", tags=["assignments"])


class AssignmentPayload(BaseModel):
    title: str = Field(..., description="作业标题")
    content: str = Field(default="", description="作业说明")
    courseId: str = Field(..., description="关联课程标识")
    allowedFileTypes: list[str] = Field(default_factory=list, description="允许的文件类型")
    maxFileSizeMB: int = Field(default=20, description="最大文件大小（MB）")
    deadline: datetime = Field(..., description="截止时间")


@router.get("", summary="作业列表")
def list_assignments(
    _user=Depends(require_roles("admin", "teacher", "student")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [serialize_assignment(a) for a in repository.list_assignments()]


def _validate(body: AssignmentPayload, repo: Repository) -> None:
    if not validate_required(body.title) or not validate_required(body.courseId):
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD)
    if not body.allowedFileTypes:
        raise http_exception_for(ErrorCode.NO_EXTENSION_SELECTED)
    if not repo.course_exists(body.courseId):
        raise http_exception_for(ErrorCode.COURSE_NOT_FOUND)


@router.post("", summary="创建作业")
def create_assignment(
    body: AssignmentPayload,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    _validate(body, repository)
    with repository.transaction():
        assignment = repository.create_assignment(
            title=body.title.strip(),
            content=body.content,
            course_id=body.courseId,
            allowed_extensions=body.allowedFileTypes,
            max_file_size_mb=body.maxFileSizeMB,
            deadline=to_naive_utc(body.deadline),
        )
    return serialize_assignment(assignment)


@router.put("/{assignment_id}", summary="更新作业")
def update_assignment(
    assignment_id: str,
    body: AssignmentPayload,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    assignment = repository.get_assignment(assignment_id)
    if assignment is None:
        raise http_exception_for(ErrorCode.ASSIGNMENT_NOT_FOUND)
    _validate(body, repository)
    with repository.transaction():
        assignment.title = body.title.strip()
        assignment.content = body.content
        assignment.course_id = body.courseId
        assignment.allowed_extensions = list(body.allowedFileTypes)
        assignment.max_file_size_mb = body.maxFileSizeMB
        assignment.deadline = to_naive_utc(body.deadline)
    return serialize_assignment(assignment)


@router.delete("/{assignment_id}", summary="删除作业")
def delete_assignment(
    assignment_id: str,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, str]:
    with repository.transaction():
        repository.delete_assignment(assignment_id)
    return {"status": "ok"}
