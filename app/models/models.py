from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
import datetime

from app.database import Base

# 班级与学生的关联表（多对多）
class_student_association = Table(
    'class_student_association',
    Base.metadata,
    Column('class_id', Integer, ForeignKey('classes.id')),
    Column('student_id', Integer, ForeignKey('users.id'))
)

# 课程与班级的关联表（多对多）
course_class_association = Table(
    'course_class_association',
    Base.metadata,
    Column('course_id', Integer, ForeignKey('courses.id')),
    Column('class_id', Integer, ForeignKey('classes.id'))
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # admin, teacher, student
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 新增字段
    avatar = Column(String, nullable=True)  # 用户头像路径
    organization = Column(String, nullable=True)  # 工作/学习单位
    id_number = Column(String, nullable=True)  # 学号/工号
    phone = Column(String, nullable=True)  # 手机号
    email = Column(String, nullable=True)  # 邮箱
    first_login = Column(Integer, default=1)  # 1表示首次登录，需要修改密码，0表示非首次登录
    
    # 关系
    classes = relationship("Class", secondary=class_student_association, back_populates="students")
    teacher_classes = relationship("Class", back_populates="teacher")
    assignments = relationship("Assignment", back_populates="teacher")
    submissions = relationship("Submission", back_populates="student")

class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 关系
    teacher = relationship("User", back_populates="teacher_classes", foreign_keys=[teacher_id])
    students = relationship("User", secondary=class_student_association, back_populates="classes")
    courses = relationship("Course", secondary=course_class_association, back_populates="classes")
    assignments = relationship("Assignment", back_populates="class_obj")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    code = Column(String, index=True)
    description = Column(String, nullable=True)
    semester = Column(String)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 关系
    classes = relationship("Class", secondary=course_class_association, back_populates="courses")
    assignments = relationship("Assignment", back_populates="course")

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    class_id = Column(Integer, ForeignKey("classes.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    teacher_id = Column(Integer, ForeignKey("users.id"))
    due_date = Column(DateTime)
    allowed_file_types = Column(String, default=".pdf,.docx")  # 默认允许pdf和docx格式
    max_file_size = Column(Integer, default=5)  # 文件大小限制，单位为MB，默认5MB
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 关系
    class_obj = relationship("Class", back_populates="assignments")
    course = relationship("Course", back_populates="assignments")
    teacher = relationship("User", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment")

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # 关系
    student = relationship("User", back_populates="submissions")
    assignment = relationship("Assignment", back_populates="submissions")
    files = relationship("File", back_populates="submission")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    filepath = Column(String)
    filesize = Column(Integer)
    filetype = Column(String)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 关系
    submission = relationship("Submission", back_populates="files") 