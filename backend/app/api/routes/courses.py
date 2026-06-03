"""课程路由（需求 7）。

* ``GET /courses`` —— 列出全部课程（前端按 ``teacherId`` 过滤）。
* ``POST /courses`` —— 创建课程并关联班级（关联当前教师）。
* ``PUT /courses/{course_id}`` —— 更新课程。
* ``DELETE /courses/{course_id}`` —— 删除课程（级联作业/提交）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_repository, require_roles
from app.api.errors import http_exception_for
from app.api.serializers import serialize_course
from app.core.errors import ErrorCode
from app.core.validators import validate_required
from app.repository import Repository

__all__ = ["router"]

router = APIRouter(prefix="/courses", tags=["courses"])


class CoursePayload(BaseModel):
    semester: str = Field(..., description="学期")
    name: str = Field(..., description="课程名称")
    classId: str = Field(..., description="关联班级标识")


@router.get("", summary="课程列表")
def list_courses(
    _user=Depends(require_roles("admin", "teacher", "student")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [serialize_course(c) for c in repository.list_courses()]


@router.post("", summary="创建课程")
def create_course(
    body: CoursePayload,
    current: CurrentUser = Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    if not (validate_required(body.semester) and validate_required(body.name) and validate_required(body.classId)):
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD)
    if not repository.class_exists(body.classId):
        raise http_exception_for(ErrorCode.CLASS_NOT_FOUND)
    teacher = repository.get_user(current.user_id)
    if teacher is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)
    with repository.transaction():
        course = repository.create_course(
            semester=body.semester.strip(),
            name=body.name.strip(),
            class_id=body.classId,
            teacher_id=teacher.id,
        )
    return serialize_course(course)


@router.put("/{course_id}", summary="更新课程")
def update_course(
    course_id: str,
    body: CoursePayload,
    _user=Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    course = repository.get_course(course_id)
    if course is None:
        raise http_exception_for(ErrorCode.COURSE_NOT_FOUND)
    if not (validate_required(body.semester) and validate_required(body.name) and validate_required(body.classId)):
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD)
    if not repository.class_exists(body.classId):
        raise http_exception_for(ErrorCode.CLASS_NOT_FOUND)
    with repository.transaction():
        course.semester = body.semester.strip()
        course.name = body.name.strip()
        course.class_id = body.classId
    return serialize_course(course)


@router.delete("/{course_id}", summary="删除课程")
def delete_course(
    course_id: str,
    _user=Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, str]:
    with repository.transaction():
        repository.delete_course(course_id)
    return {"status": "ok"}
