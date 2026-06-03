"""ORM 实体 -> 前端 JSON 形态的序列化辅助。

前端（Figma 重写版）使用 camelCase 字段命名（``teacherId`` / ``classId`` /
``createdAt`` / ``allowedFileTypes`` / ``maxFileSizeMB`` / ``submittedAt`` 等），
本模块集中负责把 SQLAlchemy 实体映射为对应的字典，供路由直接返回。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.models import Assignment, Class, Course, Submission, User

__all__ = [
    "fmt_dt",
    "serialize_user",
    "serialize_student",
    "serialize_class",
    "serialize_course",
    "serialize_assignment",
    "serialize_submission",
]

#: 统一的时间显示格式：``YYYY-MM-DD HH:MM:SS``（北京时间，见 app.core.clock）。
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def fmt_dt(value: Optional[datetime]) -> Optional[str]:
    """将 datetime 序列化为 ``YYYY-MM-DD HH:MM:SS`` 字符串；``None`` 原样返回。

    项目所有时间均为北京时间（见 :mod:`app.core.clock`），此处统一格式化为不含
    时区后缀、精确到秒的字符串（例如 ``2026-06-03 11:24:25``）。
    """
    if value is None:
        return None
    return value.strftime(DATETIME_FORMAT)


def serialize_user(user: User) -> dict[str, Any]:
    """序列化 admin / teacher 用户（含明文密码，供前端编辑回显）。"""
    return {
        "id": user.id,
        "role": user.role,
        "account": user.account,
        "name": user.name or "",
        "email": user.email or "",
        "password": user.password or "",
        "emailVerified": bool(user.email_verified),
        "createdAt": fmt_dt(user.created_at),
    }


def serialize_student(user: User) -> dict[str, Any]:
    """序列化 student 用户。"""
    return {
        "id": user.id,
        "studentId": user.student_id or "",
        "name": user.name or "",
        "email": user.email or "",
        "password": user.password or "",
        "emailVerified": bool(user.email_verified),
        "classId": user.class_id or "",
    }


def serialize_class(clazz: Class) -> dict[str, Any]:
    return {
        "id": clazz.id,
        "school": clazz.school,
        "grade": clazz.grade,
        "major": clazz.major,
        "logo": clazz.logo,
        "teacherId": clazz.teacher_id,
        "createdAt": fmt_dt(clazz.created_at),
    }


def serialize_course(course: Course) -> dict[str, Any]:
    return {
        "id": course.id,
        "semester": course.semester,
        "name": course.name,
        "classId": course.class_id,
        "teacherId": course.teacher_id,
        "createdAt": fmt_dt(course.created_at),
    }


def serialize_assignment(assignment: Assignment) -> dict[str, Any]:
    return {
        "id": assignment.id,
        "title": assignment.title,
        "content": assignment.content,
        "courseId": assignment.course_id,
        "allowedFileTypes": list(assignment.allowed_extensions),
        "maxFileSizeMB": assignment.max_file_size_mb,
        "deadline": fmt_dt(assignment.deadline),
        "createdAt": fmt_dt(assignment.created_at),
    }


def serialize_submission(submission: Submission) -> dict[str, Any]:
    return {
        "id": submission.id,
        "assignmentId": submission.assignment_id,
        "studentId": submission.student_id,
        "files": list(submission.files or []),
        "submittedAt": fmt_dt(submission.submitted_at),
        "comment": submission.comment or "",
    }
