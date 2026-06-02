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
    "iso",
    "serialize_user",
    "serialize_student",
    "serialize_class",
    "serialize_course",
    "serialize_assignment",
    "serialize_submission",
]


def iso(value: Optional[datetime]) -> Optional[str]:
    """将 datetime 序列化为 ISO-8601 字符串；``None`` 原样返回。"""
    if value is None:
        return None
    return value.isoformat()


def serialize_user(user: User) -> dict[str, Any]:
    """序列化 admin / teacher 用户（含明文密码，供前端编辑回显）。"""
    return {
        "id": user.id,
        "role": user.role,
        "account": user.account,
        "name": user.name or "",
        "email": user.email or "",
        "password": user.password or "",
        "createdAt": iso(user.created_at),
    }


def serialize_student(user: User) -> dict[str, Any]:
    """序列化 student 用户。"""
    return {
        "id": user.id,
        "studentId": user.student_id or "",
        "name": user.name or "",
        "email": user.email or "",
        "password": user.password or "",
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
        "createdAt": iso(clazz.created_at),
    }


def serialize_course(course: Course) -> dict[str, Any]:
    return {
        "id": course.id,
        "semester": course.semester,
        "name": course.name,
        "classId": course.class_id,
        "teacherId": course.teacher_id,
        "createdAt": iso(course.created_at),
    }


def serialize_assignment(assignment: Assignment) -> dict[str, Any]:
    return {
        "id": assignment.id,
        "title": assignment.title,
        "content": assignment.content,
        "courseId": assignment.course_id,
        "allowedFileTypes": list(assignment.allowed_extensions),
        "maxFileSizeMB": assignment.max_file_size_mb,
        "deadline": iso(assignment.deadline),
        "createdAt": iso(assignment.created_at),
    }


def serialize_submission(submission: Submission) -> dict[str, Any]:
    return {
        "id": submission.id,
        "assignmentId": submission.assignment_id,
        "studentId": submission.student_id,
        "files": list(submission.files or []),
        "submittedAt": iso(submission.submitted_at),
        "comment": submission.comment or "",
    }
