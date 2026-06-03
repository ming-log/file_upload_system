"""ORM 数据模型（SQLAlchemy 2.x 声明式映射）。

为对接前端（Figma 重写版）的数据形态，本模块在原有五张核心表的基础上做了如下调整：

* 角色（``User.role``）统一使用小写：``admin`` / ``teacher`` / ``student``，与前端
  ``Role`` 类型保持一致。
* 各实体补充 ``created_at`` 创建时间；``Class`` 增加可选 ``logo``（base64 data URL），
  ``Course`` 增加 ``teacher_id``（课程创建者）。
* ``Assignment.allowed_extensions`` 直接存储前端的文件类型 token（如 ``.pdf`` / ``*``），
  ``max_file_size_mb`` 放宽上限（前端滑块最大 500MB）。
* ``Submission`` 支持「一次提交多个文件 + 备注」：``files`` 以 JSON 列表存储每个文件的
  ``{name, size, type, storageId}``，并新增 ``comment`` 字段；同一学生对同一作业仅保留
  一条提交记录（重新提交即覆盖）。

字段长度上限以业务约束为准，``String(N)`` 仅作为持久化层的存储宽度提示。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.clock import now_cn_naive
from app.db import Base

__all__ = ["User", "Class", "Course", "Assignment", "Submission"]


class User(Base):
    """统一用户模型：admin、teacher、student 共用一张表，通过 ``role`` 区分。

    登录标识约定：
    * admin / teacher 通过全局唯一的 ``account`` 登录；
    * student 通过「所在学校 + 学号」登录（学号 ``student_id`` 仅在同一学校内唯一，
      不同学校可重复），学校取自其班级 :attr:`Class.school`。

    因此不再设置 ``account`` / ``student_id`` 的全局唯一约束，唯一性改由应用层
    按角色与学校上下文校验（见 repository 与各路由校验）。
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # role ∈ {admin, teacher, student}（小写，与前端一致）。
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # account：admin/teacher 的全局唯一登录标识；student 存其学号（不参与登录）。
    account: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # email_verified：学生是否已完成邮箱验证（首次登录强制验证并改密）。
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_cn_naive)

    # ---- Student 特有字段（其它角色为空） ----
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    class_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("classes.id"), nullable=True
    )

    # ---- 关系 ----
    enrolled_class: Mapped[Optional["Class"]] = relationship(
        "Class", back_populates="students", foreign_keys=[class_id]
    )
    classes_taught: Mapped[list["Class"]] = relationship(
        "Class", back_populates="teacher", foreign_keys="Class.teacher_id"
    )
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="student"
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<User id={self.id!r} role={self.role!r} account={self.account!r}>"


class Class(Base):
    """班级：学校 / 年级 / 专业，记录创建教师，可选班级 LOGO。"""

    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    school: Mapped[str] = mapped_column(String(50), nullable=False)
    grade: Mapped[str] = mapped_column(String(50), nullable=False)
    major: Mapped[str] = mapped_column(String(50), nullable=False)
    # logo：可选，前端以 base64 data URL 形式上传，存储为长文本。
    logo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_cn_naive)

    # ---- 关系 ----
    teacher: Mapped["User"] = relationship(
        "User", back_populates="classes_taught", foreign_keys=[teacher_id]
    )
    students: Mapped[list["User"]] = relationship(
        "User", back_populates="enrolled_class", foreign_keys="User.class_id"
    )
    courses: Mapped[list["Course"]] = relationship("Course", back_populates="enrolled_class")

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<Class id={self.id!r} school={self.school!r} major={self.major!r}>"


class Course(Base):
    """课程：学期 + 课程名称，关联班级与创建教师。"""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    semester: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), nullable=False)
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_cn_naive)

    # ---- 关系 ----
    enrolled_class: Mapped["Class"] = relationship("Class", back_populates="courses")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="course"
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<Course id={self.id!r} name={self.name!r} semester={self.semester!r}>"


class Assignment(Base):
    """作业：标题 / 说明 / 关联课程 / 提交约束（扩展名、大小、截止时间）。"""

    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey("courses.id"), nullable=False)
    # allowed_extensions：前端文件类型 token 列表（如 ".pdf" / ".zip" / "*"）。
    allowed_extensions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_cn_naive)

    # ---- 关系 ----
    course: Mapped["Course"] = relationship("Course", back_populates="assignments")
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="assignment"
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<Assignment id={self.id!r} title={self.title!r} course_id={self.course_id!r}>"


class Submission(Base):
    """作业提交记录：关联学生与作业，支持多文件 + 备注。"""

    __tablename__ = "submissions"
    __table_args__ = (
        # 同一学生对同一作业仅保留一条记录（重新提交覆盖）。
        UniqueConstraint("student_id", "assignment_id", name="uq_submissions_student_assignment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assignments.id"), nullable=False
    )
    # files：JSON 列表，每项形如 {"name", "size", "type", "storageId"}。
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # ---- 关系 ----
    student: Mapped["User"] = relationship(
        "User", back_populates="submissions", foreign_keys=[student_id]
    )
    assignment: Mapped["Assignment"] = relationship("Assignment", back_populates="submissions")

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return (
            f"<Submission id={self.id!r} student_id={self.student_id!r} "
            f"assignment_id={self.assignment_id!r}>"
        )
