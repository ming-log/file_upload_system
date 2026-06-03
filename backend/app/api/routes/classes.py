"""班级与学生路由（需求 5、6）。

班级（teacher 职能）：

* ``GET /classes`` —— 列出全部班级（前端按 ``teacherId`` 过滤当前教师）。
* ``POST /classes`` —— 创建班级（关联当前教师）。
* ``PUT /classes/{class_id}`` —— 更新班级。
* ``DELETE /classes/{class_id}`` —— 删除班级（级联学生/课程/作业/提交）。

班级内学生：

* ``GET /classes/{class_id}/students`` —— 列出班级学生。
* ``POST /classes/{class_id}/students`` —— 创建学生（账号即学号）。
* ``PUT /students/{student_id}`` —— 更新学生。
* ``DELETE /students/{student_id}`` —— 删除学生。
* ``POST /classes/{class_id}/students/batch`` —— 批量导入学生。
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_repository, require_roles
from app.api.errors import http_exception_for
from app.api.serializers import serialize_class, serialize_student
from app.core.errors import ErrorCode
from app.core.validators import DEFAULT_PASSWORD, validate_email, validate_required
from app.repository import Repository

__all__ = ["router"]

router = APIRouter(tags=["classes"])


# --------------------------------------------------------------------------- #
# 模型                                                                          #
# --------------------------------------------------------------------------- #


class ClassPayload(BaseModel):
    school: str = Field(..., description="学校")
    grade: str = Field(..., description="年级")
    major: str = Field(..., description="专业")
    logo: Optional[str] = Field(default=None, description="班级 LOGO（base64 data URL）")


class StudentPayload(BaseModel):
    studentId: str = Field(..., description="学号（系统内唯一）")
    name: str = Field(..., description="姓名")
    email: str = Field(..., description="邮箱（必填）")
    password: str = Field(default="", description="密码，留空默认 minglog666")


class BatchStudentsRequest(BaseModel):
    records: list[StudentPayload] = Field(default_factory=list)


class BatchFailureModel(BaseModel):
    row_id: int | str
    reason: str


class BatchResultResponse(BaseModel):
    success_count: int
    failure_count: int
    failures: list[BatchFailureModel] = Field(default_factory=list)


def _resolve_teacher_id(repo: Repository, current: CurrentUser) -> str:
    teacher = repo.get_user_by_account(current.account)
    if teacher is None:
        raise http_exception_for(ErrorCode.FORBIDDEN)
    return teacher.id


def _validate_student(
    repo: Repository, body: StudentPayload, *, exclude_id: Optional[str] = None
) -> Optional[ErrorCode]:
    if not validate_required(body.studentId) or not validate_required(body.name):
        return ErrorCode.MISSING_REQUIRED_FIELD
    # 邮箱为必填项。
    if not validate_required(body.email):
        return ErrorCode.MISSING_REQUIRED_FIELD
    if not validate_email(body.email).ok:
        return ErrorCode.INVALID_EMAIL_FORMAT
    if repo.student_id_exists(body.studentId, exclude_id=exclude_id):
        return ErrorCode.DUPLICATE_STUDENT_ID
    if repo.account_exists(body.studentId, exclude_id=exclude_id):
        return ErrorCode.DUPLICATE_ACCOUNT
    return None


# --------------------------------------------------------------------------- #
# 班级                                                                          #
# --------------------------------------------------------------------------- #


@router.get("/classes", summary="班级列表")
def list_classes(
    _user=Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [serialize_class(c) for c in repository.list_classes()]


@router.post("/classes", summary="创建班级")
def create_class(
    body: ClassPayload,
    current: CurrentUser = Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    if not (validate_required(body.school) and validate_required(body.grade) and validate_required(body.major)):
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD)
    teacher_id = _resolve_teacher_id(repository, current)
    with repository.transaction():
        clazz = repository.create_class(
            school=body.school.strip(),
            grade=body.grade.strip(),
            major=body.major.strip(),
            logo=body.logo,
            teacher_id=teacher_id,
        )
    return serialize_class(clazz)


@router.put("/classes/{class_id}", summary="更新班级")
def update_class(
    class_id: str,
    body: ClassPayload,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    clazz = repository.get_class(class_id)
    if clazz is None:
        raise http_exception_for(ErrorCode.CLASS_NOT_FOUND)
    if not (validate_required(body.school) and validate_required(body.grade) and validate_required(body.major)):
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD)
    with repository.transaction():
        clazz.school = body.school.strip()
        clazz.grade = body.grade.strip()
        clazz.major = body.major.strip()
        clazz.logo = body.logo
    return serialize_class(clazz)


@router.delete("/classes/{class_id}", summary="删除班级")
def delete_class(
    class_id: str,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, str]:
    with repository.transaction():
        repository.delete_class(class_id)
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# 学生                                                                          #
# --------------------------------------------------------------------------- #


@router.get("/classes/{class_id}/students", summary="班级学生列表")
def list_students(
    class_id: str,
    _user=Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [serialize_student(s) for s in repository.list_students(class_id=class_id)]


@router.get("/students", summary="全部学生列表")
def list_all_students(
    _user=Depends(require_roles("admin", "teacher")),
    repository: Repository = Depends(get_repository),
) -> list[dict[str, Any]]:
    return [serialize_student(s) for s in repository.list_students()]


@router.post("/classes/{class_id}/students", summary="创建学生")
def create_student(
    class_id: str,
    body: StudentPayload,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    if repository.get_class(class_id) is None:
        raise http_exception_for(ErrorCode.CLASS_NOT_FOUND)
    error = _validate_student(repository, body)
    if error is not None:
        raise http_exception_for(error)
    with repository.transaction():
        student = repository.create_user(
            role="student",
            account=body.studentId.strip(),
            name=body.name.strip(),
            email=body.email.strip(),
            password=body.password.strip() or DEFAULT_PASSWORD,
            student_id=body.studentId.strip(),
            class_id=class_id,
        )
    return serialize_student(student)


@router.put("/students/{student_id}", summary="更新学生")
def update_student(
    student_id: str,
    body: StudentPayload,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, Any]:
    student = repository.get_user(student_id)
    if student is None or student.role != "student":
        raise http_exception_for(ErrorCode.MISSING_REQUIRED_FIELD, message="学生不存在")
    error = _validate_student(repository, body, exclude_id=student_id)
    if error is not None:
        raise http_exception_for(error)
    with repository.transaction():
        student.student_id = body.studentId.strip()
        student.account = body.studentId.strip()
        student.name = body.name.strip()
        student.email = body.email.strip()
        if body.password.strip():
            student.password = body.password.strip()
    return serialize_student(student)


@router.delete("/students/{student_id}", summary="删除学生")
def delete_student(
    student_id: str,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> dict[str, str]:
    with repository.transaction():
        repository.delete_student(student_id)
    return {"status": "ok"}


@router.post(
    "/classes/{class_id}/students/batch",
    response_model=BatchResultResponse,
    summary="批量导入学生",
)
def batch_import_students(
    class_id: str,
    body: BatchStudentsRequest,
    _user=Depends(require_roles("teacher")),
    repository: Repository = Depends(get_repository),
) -> BatchResultResponse:
    if repository.get_class(class_id) is None:
        raise http_exception_for(ErrorCode.CLASS_NOT_FOUND)
    if not body.records:
        raise http_exception_for(ErrorCode.EMPTY_BATCH)

    failures: list[BatchFailureModel] = []
    success = 0
    seen: set[str] = set()
    with repository.transaction():
        for index, rec in enumerate(body.records):
            row_id: int | str = rec.studentId.strip() if validate_required(rec.studentId) else index
            error = _validate_student(repository, rec)
            if error is None and rec.studentId.strip() in seen:
                error = ErrorCode.DUPLICATE_STUDENT_ID
            if error is not None:
                failures.append(BatchFailureModel(row_id=row_id, reason=error.value))
                continue
            repository.create_user(
                role="student",
                account=rec.studentId.strip(),
                name=rec.name.strip(),
                email=rec.email.strip(),
                password=rec.password.strip() or DEFAULT_PASSWORD,
                student_id=rec.studentId.strip(),
                class_id=class_id,
            )
            seen.add(rec.studentId.strip())
            success += 1
    return BatchResultResponse(
        success_count=success, failure_count=len(failures), failures=failures
    )
