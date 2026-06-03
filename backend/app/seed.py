"""初始数据播种（开发/本地联调用）。

系统默认使用文件 SQLite，首次启动时数据库为空。本模块在应用启动时**幂等地**写入
一套与前端演示账号一致的初始数据，使前端可立即登录体验：

* 管理员：``admin / admin123``
* 教师：``teacher001 / teacher123``（张伟）
* 学生：``2022001 / minglog666`` 等

仅当系统内尚不存在管理员账号时才播种（幂等，重复启动不会重复插入）。可通过环境变量
``SEED_DISABLE=1`` 关闭。
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.clock import now_cn_naive
from app.repository import Repository

logger = logging.getLogger(__name__)

SEED_ADMIN_ACCOUNT: str = os.getenv("SEED_ADMIN_ACCOUNT", "admin")
SEED_ADMIN_PASSWORD: str = os.getenv("SEED_ADMIN_PASSWORD", "admin123")
SEED_ADMIN_EMAIL: str = os.getenv("SEED_ADMIN_EMAIL", "admin@school.edu")


def seed_initial_data(session: Session) -> bool:
    """若系统内不存在管理员账号，则写入一套演示数据（幂等）。

    Returns:
        ``True`` 表示本次完成了播种；``False`` 表示已存在、跳过。
    """
    repo = Repository(session)
    if repo.get_user_by_account(SEED_ADMIN_ACCOUNT) is not None:
        logger.info("初始数据已存在，跳过播种")
        return False

    now = now_cn_naive()
    with repo.transaction():
        # 管理员。
        repo.create_user(
            id="user-1",
            role="admin",
            account=SEED_ADMIN_ACCOUNT,
            name="系统管理员",
            email=SEED_ADMIN_EMAIL,
            password=SEED_ADMIN_PASSWORD,
            created_at=now,
        )
        # 教师。
        teacher = repo.create_user(
            id="user-2",
            role="teacher",
            account="teacher001",
            name="张伟",
            email="zhangwei@school.edu",
            password="teacher123",
            created_at=now,
        )
        # 班级。
        clazz = repo.create_class(
            id="class-1",
            school="清华大学",
            grade="2022级",
            major="软件工程",
            teacher_id=teacher.id,
            created_at=now,
        )
        # 学生。
        students = [
            ("2022001", "李明", "liming@stu.edu"),
            ("2022002", "王芳", "wangfang@stu.edu"),
            ("2022003", "刘强", "liuqiang@stu.edu"),
        ]
        for sid, name, email in students:
            repo.create_user(
                role="student",
                account=sid,
                name=name,
                email=email,
                password="minglog666",
                student_id=sid,
                class_id=clazz.id,
                created_at=now,
            )
        # 课程。
        course1 = repo.create_course(
            id="course-1",
            semester="2024春季学期",
            name="Web前端开发",
            class_id=clazz.id,
            teacher_id=teacher.id,
            created_at=now,
        )
        course2 = repo.create_course(
            id="course-2",
            semester="2024春季学期",
            name="数据结构与算法",
            class_id=clazz.id,
            teacher_id=teacher.id,
            created_at=now,
        )
        # 作业。
        repo.create_assignment(
            id="assign-1",
            title="React组件开发实践",
            content="请使用React开发一个待办事项应用，要求包含添加、删除、标记完成等功能，提交源代码压缩包。",
            course_id=course1.id,
            allowed_extensions=[".zip", ".rar"],
            max_file_size_mb=50,
            deadline=now + timedelta(days=30),
            created_at=now,
        )
        repo.create_assignment(
            id="assign-2",
            title="链表排序算法实现",
            content="用Java或C++实现链表的归并排序，要求时间复杂度O(nlogn)，提交源代码及实验报告。",
            course_id=course2.id,
            allowed_extensions=[".zip", ".pdf", ".docx"],
            max_file_size_mb=20,
            deadline=now + timedelta(days=15),
            created_at=now,
        )

    logger.info("已写入初始演示数据（管理员/教师/学生/班级/课程/作业）")
    return True
