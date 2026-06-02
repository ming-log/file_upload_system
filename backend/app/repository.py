"""Repository 层：封装数据库访问（全量 CRUD）。

为对接前端（Figma 重写版）的增删改查需求，本层在原有「创建 + 查重 + 事务」的基础上
扩展为对五张核心表的完整 CRUD 能力：列表、按主键读取、创建、更新、删除，以及级联
删除（删除班级/课程/作业时一并清理其下属记录，避免孤立数据）。

设计要点：

* 构造时接收一个 :class:`~sqlalchemy.orm.Session`（由 :mod:`app.db` 会话工厂创建），
  生产与测试均可注入。
* 写操作统一通过 :meth:`Repository.transaction` 上下文管理器保证原子性。
* 主键统一使用 ``uuid4().hex``；调用方未显式提供时自动生成。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, Class, Course, Submission, User

__all__ = ["Repository", "new_id"]


def new_id() -> str:
    """生成 32 位十六进制主键标识。"""
    return uuid.uuid4().hex


class Repository:
    """封装五张核心表的数据库访问、查询与事务边界。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    # ------------------------------------------------------------------ #
    # 事务边界                                                            #
    # ------------------------------------------------------------------ #

    @contextmanager
    def transaction(self) -> Iterator["Repository"]:
        """事务上下文：正常退出提交，异常回滚并重新抛出。"""
        try:
            yield self
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def commit(self) -> None:
        self._session.commit()

    def flush(self) -> None:
        self._session.flush()

    # ------------------------------------------------------------------ #
    # 唯一性 / 存在性                                                     #
    # ------------------------------------------------------------------ #

    def account_exists(self, account: str, *, exclude_id: Optional[str] = None) -> bool:
        stmt = select(User.id).where(User.account == account)
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return self._session.scalar(stmt.limit(1)) is not None

    def student_id_exists(self, student_id: str, *, exclude_id: Optional[str] = None) -> bool:
        stmt = select(User.id).where(User.student_id == student_id)
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return self._session.scalar(stmt.limit(1)) is not None

    def class_exists(self, class_id: str) -> bool:
        return self._session.scalar(select(Class.id).where(Class.id == class_id).limit(1)) is not None

    def course_exists(self, course_id: str) -> bool:
        return self._session.scalar(select(Course.id).where(Course.id == course_id).limit(1)) is not None

    def assignment_exists(self, assignment_id: str) -> bool:
        return (
            self._session.scalar(select(Assignment.id).where(Assignment.id == assignment_id).limit(1))
            is not None
        )

    # ------------------------------------------------------------------ #
    # 查询：单条                                                          #
    # ------------------------------------------------------------------ #

    def get_user(self, user_id: str) -> Optional[User]:
        return self._session.get(User, user_id)

    def get_user_by_account(self, account: str) -> Optional[User]:
        return self._session.scalar(select(User).where(User.account == account).limit(1))

    def get_class(self, class_id: str) -> Optional[Class]:
        return self._session.get(Class, class_id)

    def get_course(self, course_id: str) -> Optional[Course]:
        return self._session.get(Course, course_id)

    def get_assignment(self, assignment_id: str) -> Optional[Assignment]:
        return self._session.get(Assignment, assignment_id)

    def get_submission(self, submission_id: str) -> Optional[Submission]:
        return self._session.get(Submission, submission_id)

    def get_submission_for(self, student_id: str, assignment_id: str) -> Optional[Submission]:
        stmt = (
            select(Submission)
            .where(Submission.student_id == student_id, Submission.assignment_id == assignment_id)
            .limit(1)
        )
        return self._session.scalar(stmt)

    # ------------------------------------------------------------------ #
    # 查询：列表                                                          #
    # ------------------------------------------------------------------ #

    def list_users(self, *, roles: Optional[Sequence[str]] = None) -> list[User]:
        stmt = select(User)
        if roles is not None:
            stmt = stmt.where(User.role.in_(list(roles)))
        return list(self._session.scalars(stmt).all())

    def list_students(self, *, class_id: Optional[str] = None) -> list[User]:
        stmt = select(User).where(User.role == "student")
        if class_id is not None:
            stmt = stmt.where(User.class_id == class_id)
        return list(self._session.scalars(stmt).all())

    def list_classes(self) -> list[Class]:
        return list(self._session.scalars(select(Class)).all())

    def list_courses(self) -> list[Course]:
        return list(self._session.scalars(select(Course)).all())

    def list_assignments(self) -> list[Assignment]:
        return list(self._session.scalars(select(Assignment)).all())

    def list_submissions(self) -> list[Submission]:
        return list(self._session.scalars(select(Submission)).all())

    # ------------------------------------------------------------------ #
    # 创建                                                                #
    # ------------------------------------------------------------------ #

    def create_user(
        self,
        *,
        role: str,
        account: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        student_id: Optional[str] = None,
        class_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        id: Optional[str] = None,
    ) -> User:
        user = User(
            id=id or new_id(),
            role=role,
            account=account,
            name=name,
            email=email,
            password=password,
            student_id=student_id,
            class_id=class_id,
            created_at=created_at or datetime.utcnow(),
        )
        self._session.add(user)
        self._session.flush()
        return user

    def create_class(
        self,
        *,
        school: str,
        grade: str,
        major: str,
        teacher_id: str,
        logo: Optional[str] = None,
        created_at: Optional[datetime] = None,
        id: Optional[str] = None,
    ) -> Class:
        clazz = Class(
            id=id or new_id(),
            school=school,
            grade=grade,
            major=major,
            logo=logo,
            teacher_id=teacher_id,
            created_at=created_at or datetime.utcnow(),
        )
        self._session.add(clazz)
        self._session.flush()
        return clazz

    def create_course(
        self,
        *,
        semester: str,
        name: str,
        class_id: str,
        teacher_id: str,
        created_at: Optional[datetime] = None,
        id: Optional[str] = None,
    ) -> Course:
        course = Course(
            id=id or new_id(),
            semester=semester,
            name=name,
            class_id=class_id,
            teacher_id=teacher_id,
            created_at=created_at or datetime.utcnow(),
        )
        self._session.add(course)
        self._session.flush()
        return course

    def create_assignment(
        self,
        *,
        title: str,
        course_id: str,
        allowed_extensions: Sequence[str],
        deadline: datetime,
        content: str = "",
        max_file_size_mb: int = 5,
        created_at: Optional[datetime] = None,
        id: Optional[str] = None,
    ) -> Assignment:
        assignment = Assignment(
            id=id or new_id(),
            title=title,
            content=content,
            course_id=course_id,
            allowed_extensions=list(allowed_extensions),
            max_file_size_mb=max_file_size_mb,
            deadline=deadline,
            created_at=created_at or datetime.utcnow(),
        )
        self._session.add(assignment)
        self._session.flush()
        return assignment

    def create_submission(
        self,
        *,
        student_id: str,
        assignment_id: str,
        files: Sequence[dict[str, Any]],
        comment: str,
        submitted_at: datetime,
        id: Optional[str] = None,
    ) -> Submission:
        submission = Submission(
            id=id or new_id(),
            student_id=student_id,
            assignment_id=assignment_id,
            files=list(files),
            comment=comment,
            submitted_at=submitted_at,
        )
        self._session.add(submission)
        self._session.flush()
        return submission

    def upsert_submission(
        self,
        *,
        student_id: str,
        assignment_id: str,
        files: Sequence[dict[str, Any]],
        comment: str,
        submitted_at: datetime,
    ) -> Submission:
        """学生对同一作业重复提交时覆盖既有记录，否则新建。"""
        existing = self.get_submission_for(student_id, assignment_id)
        if existing is not None:
            existing.files = list(files)
            existing.comment = comment
            existing.submitted_at = submitted_at
            self._session.flush()
            return existing
        return self.create_submission(
            student_id=student_id,
            assignment_id=assignment_id,
            files=files,
            comment=comment,
            submitted_at=submitted_at,
        )

    # ------------------------------------------------------------------ #
    # 删除（含级联）                                                      #
    # ------------------------------------------------------------------ #

    def delete_user(self, user_id: str) -> None:
        user = self._session.get(User, user_id)
        if user is not None:
            self._session.delete(user)
            self._session.flush()

    def delete_student(self, student_id: str) -> None:
        """删除学生并清理其提交记录。"""
        student = self._session.get(User, student_id)
        if student is None:
            return
        for sub in list(student.submissions):
            self._session.delete(sub)
        self._session.delete(student)
        self._session.flush()

    def delete_class(self, class_id: str) -> None:
        """删除班级：级联删除其学生、课程、课程下作业及相关提交记录。"""
        clazz = self._session.get(Class, class_id)
        if clazz is None:
            return
        # 课程 -> 作业 -> 提交。
        for course in self.list_courses():
            if course.class_id == class_id:
                self.delete_course(course.id)
        # 学生及其提交。
        for student in self.list_students(class_id=class_id):
            self.delete_student(student.id)
        self._session.delete(clazz)
        self._session.flush()

    def delete_course(self, course_id: str) -> None:
        """删除课程：级联删除其作业及相关提交记录。"""
        course = self._session.get(Course, course_id)
        if course is None:
            return
        for assignment in self.list_assignments():
            if assignment.course_id == course_id:
                self.delete_assignment(assignment.id)
        self._session.delete(course)
        self._session.flush()

    def delete_assignment(self, assignment_id: str) -> None:
        """删除作业并清理其提交记录。"""
        assignment = self._session.get(Assignment, assignment_id)
        if assignment is None:
            return
        for sub in list(assignment.submissions):
            self._session.delete(sub)
        self._session.delete(assignment)
        self._session.flush()
