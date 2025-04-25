from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

# 用户相关模式
class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class UserInDB(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class User(UserInDB):
    pass

# 班级相关模式
class ClassBase(BaseModel):
    name: str
    description: Optional[str] = None

class ClassCreate(ClassBase):
    pass

class ClassUpdate(ClassBase):
    pass

class ClassInDB(ClassBase):
    id: int
    teacher_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class Class(ClassInDB):
    teacher: User
    students: List[User] = []
    
    class Config:
        from_attributes = True

# 课程相关模式
class CourseBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    semester: str

class CourseCreate(CourseBase):
    pass

class CourseUpdate(CourseBase):
    pass

class CourseInDB(CourseBase):
    id: int
    teacher_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class Course(CourseInDB):
    class Config:
        from_attributes = True

# 作业相关模式
class AssignmentBase(BaseModel):
    title: str
    description: str
    class_id: int
    course_id: int
    due_date: datetime

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentUpdate(AssignmentBase):
    pass

class AssignmentInDB(AssignmentBase):
    id: int
    teacher_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class Assignment(AssignmentInDB):
    class_obj: Class
    course: Course
    
    class Config:
        from_attributes = True

# 文件相关模式
class FileBase(BaseModel):
    filename: str
    filesize: int
    filetype: str

class FileCreate(FileBase):
    filepath: str
    submission_id: int

class FileInDB(FileBase):
    id: int
    filepath: str
    submission_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class File(FileInDB):
    class Config:
        from_attributes = True

# 提交相关模式
class SubmissionBase(BaseModel):
    assignment_id: int
    student_id: int

class SubmissionCreate(SubmissionBase):
    pass

class SubmissionInDB(SubmissionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class Submission(SubmissionInDB):
    files: List[File] = []
    
    class Config:
        from_attributes = True

# 身份验证相关模式
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 统计信息相关模式
class AdminStats(BaseModel):
    users_count: int
    classes_count: int
    courses_count: int
    uploads_count: int

class TeacherStats(BaseModel):
    my_classes_count: int
    my_courses_count: int
    my_assignments_count: int
    student_submissions_count: int

class StudentStats(BaseModel):
    my_classes_count: int
    assignments_count: int
    completed_assignments: int
    uploads_count: int 