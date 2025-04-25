from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Course, Class
from app.schemas import Course as CourseSchema, CourseCreate, CourseUpdate
from app.auth import get_current_user, teacher_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/courses", response_class=HTMLResponse, name="courses")
async def list_courses(
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    courses = db.query(Course).filter(Course.teacher_id == current_user.id).all()
    return templates.TemplateResponse(
        "courses.html",
        {"request": request, "user": current_user, "courses": courses}
    )

@router.get("/courses/create", response_class=HTMLResponse, name="create_course")
async def create_course_page(
    request: Request,
    current_user: User = Depends(teacher_required)
):
    return templates.TemplateResponse(
        "course_form.html",
        {"request": request, "user": current_user}
    )

@router.post("/courses/create", name="create_course")
async def create_course(
    course_name: str = Form(...),
    course_code: str = Form(...),
    description: str = Form(None),
    semester: str = Form(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 创建新课程
    new_course = Course(
        name=course_name,
        code=course_code,
        description=description,
        semester=semester,
        teacher_id=current_user.id
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    
    return RedirectResponse(url="/courses", status_code=303)

@router.get("/courses/{course_id}", response_class=HTMLResponse, name="view_course")
async def view_course(
    course_id: int,
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 确保只有课程的创建者可以查看
    if course.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问此课程")
    
    # 获取关联班级
    associated_classes = course.classes
    
    # 获取关联作业
    course_assignments = course.assignments
    
    # 为每个作业添加提交统计信息
    for assignment in course_assignments:
        assignment.submissions_count = len(assignment.submissions)
        assignment.total_students = len(assignment.class_obj.students) if assignment.class_obj else 0
    
    return templates.TemplateResponse(
        "course_form.html",
        {
            "request": request, 
            "user": current_user, 
            "course": course,
            "associated_classes": associated_classes,
            "course_assignments": course_assignments
        }
    )

@router.post("/courses/{course_id}/update", name="update_course")
async def update_course(
    course_id: int,
    course_name: str = Form(...),
    course_code: str = Form(...),
    description: str = Form(None),
    semester: str = Form(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 确保只有课程的创建者可以更新
    if course.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此课程")
    
    # 更新课程信息
    course.name = course_name
    course.code = course_code
    course.description = description
    course.semester = semester
    
    db.commit()
    
    return RedirectResponse(url=f"/courses/{course_id}", status_code=303)

@router.get("/api/classes/{class_id}/courses", name="get_class_courses")
async def get_class_courses(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取班级关联的课程，用于动态更新课程下拉框"""
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只有班级的创建者或管理员可以查看
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问此班级")
    
    courses = []
    for course in class_obj.courses:
        courses.append({
            "id": course.id,
            "name": course.name
        })
    
    return {"courses": courses} 