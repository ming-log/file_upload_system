from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Class, Course, Assignment, Submission, File
from app.schemas import AdminStats, TeacherStats, StudentStats
from app.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse, name="dashboard")
async def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    password_changed: bool = False,
    profile_updated: bool = False
):
    """根据用户角色显示相应的仪表盘"""
    
    # 管理员仪表盘
    if current_user.role == "admin":
        # 获取统计数据
        users_count = db.query(User).count()
        classes_count = db.query(Class).count()
        courses_count = db.query(Course).count()
        uploads_count = db.query(File).count()
        
        stats = AdminStats(
            users_count=users_count,
            classes_count=classes_count,
            courses_count=courses_count,
            uploads_count=uploads_count
        )
        
        # 获取最近创建的用户
        recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request, 
                "user": current_user, 
                "stats": stats,
                "recent_users": recent_users,
                "password_changed": password_changed,
                "profile_updated": profile_updated
            }
        )
    
    # 教师仪表盘
    elif current_user.role == "teacher":
        # 获取教师相关的班级
        teacher_classes = db.query(Class).filter(Class.teacher_id == current_user.id).all()
        
        # 获取教师相关的课程
        teacher_courses = db.query(Course).filter(Course.teacher_id == current_user.id).all()
        
        # 获取教师相关的作业
        teacher_assignments = db.query(Assignment).filter(Assignment.teacher_id == current_user.id).all()
        
        # 获取学生提交量
        class_ids = [class_obj.id for class_obj in teacher_classes]
        assignment_ids = [assignment.id for assignment in teacher_assignments]
        
        # 获取相关的提交
        submissions_count = db.query(Submission).filter(Submission.assignment_id.in_(assignment_ids)).count()
        
        # 统计信息
        stats = TeacherStats(
            my_classes_count=len(teacher_classes),
            my_courses_count=len(teacher_courses),
            my_assignments_count=len(teacher_assignments),
            student_submissions_count=submissions_count
        )
        
        # 获取最近的作业
        recent_assignments = db.query(Assignment).filter(
            Assignment.teacher_id == current_user.id
        ).order_by(Assignment.created_at.desc()).limit(5).all()
        
        # 为每个作业添加提交统计信息
        for assignment in recent_assignments:
            assignment.submissions_count = db.query(Submission).filter(Submission.assignment_id == assignment.id).count()
            assignment.total_students = len(assignment.class_obj.students) if assignment.class_obj else 0
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request, 
                "user": current_user, 
                "stats": stats,
                "teacher_classes": teacher_classes,
                "recent_assignments": recent_assignments,
                "password_changed": password_changed,
                "profile_updated": profile_updated
            }
        )
    
    # 学生仪表盘
    elif current_user.role == "student":
        # 获取学生所在的班级
        student_classes = current_user.classes
        
        # 获取相关的作业
        class_ids = [class_obj.id for class_obj in student_classes]
        if class_ids:
            assignments = db.query(Assignment).filter(Assignment.class_id.in_(class_ids)).all()
        else:
            assignments = []
        
        # 获取已完成的作业
        student_submissions = db.query(Submission).filter(Submission.student_id == current_user.id).all()
        completed_assignment_ids = [submission.assignment_id for submission in student_submissions]
        
        # 标记作业状态
        for assignment in assignments:
            if assignment.id in completed_assignment_ids:
                assignment.status = "submitted"
            else:
                assignment.status = "pending"
        
        # 计算待完成和已完成的作业
        pending_assignments = [a for a in assignments if a.status == "pending"]
        completed_assignments = [a for a in assignments if a.status == "submitted"]
        
        # 获取上传文件数量
        uploads_count = db.query(File).join(Submission).filter(Submission.student_id == current_user.id).count()
        
        # 统计信息
        stats = StudentStats(
            my_classes_count=len(student_classes),
            assignments_count=len(pending_assignments),
            completed_assignments=len(completed_assignments),
            uploads_count=uploads_count
        )
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request, 
                "user": current_user, 
                "stats": stats,
                "pending_assignments": pending_assignments,
                "password_changed": password_changed,
                "profile_updated": profile_updated
            }
        )
    
    # 未知角色
    else:
        raise HTTPException(status_code=403, detail="未知用户角色") 