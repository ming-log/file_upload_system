from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Course, Class, Assignment, Submission, File
from app.schemas import Course as CourseSchema, CourseCreate, CourseUpdate
from app.auth import get_current_user, teacher_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/courses", response_class=HTMLResponse, name="courses")
async def list_courses(
    request: Request,
    page: int = 1,
    per_page: int = 8,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 构建基础查询
    if current_user.role == "admin":
        base_query = db.query(Course)
    else:
        # 教师只看到自己的课程
        base_query = db.query(Course).filter(Course.teacher_id == current_user.id)
    
    # 计算总数和总页数
    total = base_query.count()
    total_pages = (total + per_page - 1) // per_page  # 向上取整
    
    # 分页查询
    courses = base_query.order_by(Course.id).offset((page - 1) * per_page).limit(per_page).all()
    
    # 创建分页对象
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_num": page - 1 if page > 1 else None,
        "next_num": page + 1 if page < total_pages else None,
        "iter_pages": lambda left_edge=2, right_edge=2, left_current=2, right_current=2: _iter_pages(
            page, total_pages, left_edge, right_edge, left_current, right_current
        )
    }
    
    # 计算统计数据
    stats = {
        "total_courses": total,
        "total_assignments": None,
        "total_students": None
    }
    
    # 计算当前用户的课程相关的统计数据
    if current_user.role == "admin":
        # 管理员查看全系统的统计
        stats["total_assignments"] = db.query(Assignment).count()
        
        # 计算参与课程的学生总数（去重）
        from sqlalchemy import func, distinct
        student_count = db.query(func.count(distinct(User.id))).join(
            Class.students
        ).join(
            Class.courses
        ).scalar()
        stats["total_students"] = student_count
    else:
        # 教师查看自己课程的统计
        teacher_assignments = db.query(Assignment).join(
            Course, Assignment.course_id == Course.id
        ).filter(
            Course.teacher_id == current_user.id
        ).count()
        stats["total_assignments"] = teacher_assignments
        
        # 计算参与该教师课程的学生总数（去重）
        from sqlalchemy import func, distinct
        student_count = db.query(func.count(distinct(User.id))).join(
            Class.students
        ).join(
            Class.courses
        ).filter(
            Course.teacher_id == current_user.id
        ).scalar()
        stats["total_students"] = student_count
    
    return templates.TemplateResponse(
        "courses.html",
        {
            "request": request, 
            "user": current_user, 
            "courses": courses,
            "pagination": pagination,
            "stats": stats
        }
    )

def _iter_pages(page, total_pages, left_edge=2, right_edge=2, left_current=2, right_current=2):
    """辅助函数，用于生成分页序列"""
    last = 0
    for num in range(1, total_pages + 1):
        if num <= left_edge or \
           (num > page - left_current - 1 and num < page + right_current) or \
           num > total_pages - right_edge:
            if last + 1 != num:
                yield None
            yield num
            last = num

@router.get("/courses/create", response_class=HTMLResponse, name="create_course")
async def create_course_page(
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 获取教师创建的班级列表或管理员可以看到所有班级
    if current_user.role == "admin":
        available_classes = db.query(Class).all()
    else:
        available_classes = db.query(Class).filter(Class.teacher_id == current_user.id).all()
    
    return templates.TemplateResponse(
        "course_form.html",
        {
            "request": request, 
            "user": current_user,
            "available_classes": available_classes
        }
    )

@router.post("/courses/create", name="create_course")
async def create_course(
    course_name: str = Form(...),
    course_code: str = Form(...),
    description: str = Form(None),
    semester: str = Form(...),
    classes: List[int] = Form([]),
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
    
    # 关联选择的班级
    if classes:
        for class_id in classes:
            class_obj = db.query(Class).filter(Class.id == class_id).first()
            # 管理员可以关联任何班级，教师只能关联自己的班级
            if class_obj and (class_obj.teacher_id == current_user.id or current_user.role == "admin"):
                new_course.classes.append(class_obj)
        
        db.commit()
    
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
    
    # 获取可用于关联的班级
    if current_user.role == "admin":
        # 管理员可以看到所有班级
        available_classes = db.query(Class).filter(
            ~Class.id.in_([c.id for c in associated_classes])
        ).all()
    else:
        # 教师只能看到自己的班级
        available_classes = db.query(Class).filter(
            Class.teacher_id == current_user.id,
            ~Class.id.in_([c.id for c in associated_classes])
        ).all()
    
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
            "available_classes": available_classes,
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
    classes: List[int] = Form([]),
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

@router.post("/courses/{course_id}/classes/add", name="add_class_to_course")
async def add_class_to_course(
    course_id: int,
    class_id: int = Form(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 确保只有课程的创建者可以添加班级
    if course.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此课程")
    
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只能关联自己创建的班级
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权关联此班级")
    
    # 检查班级是否已关联到课程
    if class_obj in course.classes:
        raise HTTPException(status_code=400, detail="班级已关联到此课程")
    
    # 添加班级到课程
    course.classes.append(class_obj)
    db.commit()
    
    return RedirectResponse(url=f"/courses/{course_id}", status_code=303)

@router.post("/courses/{course_id}/classes/{class_id}/remove", name="remove_class_from_course")
async def remove_class_from_course(
    course_id: int,
    class_id: int,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 确保只有课程的创建者可以移除班级
    if course.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此课程")
    
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 移除班级
    if class_obj in course.classes:
        course.classes.remove(class_obj)
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

@router.get("/delete_course/{course_id}", name="delete_course")
async def delete_course(
    course_id: int,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    """删除课程"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 确保只有课程的创建者或管理员可以删除
    if course.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权删除此课程")
    
    # 删除课程前先解除相关关联
    course.classes = []
    
    # 获取与课程相关的作业
    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).all()
    
    # 删除作业及其相关提交
    for assignment in assignments:
        # 查找相关提交
        submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
        
        # 删除每个提交及其关联文件
        for submission in submissions:
            # 删除文件
            db.query(File).filter(File.submission_id == submission.id).delete()
            # 删除提交
            db.delete(submission)
        
        # 删除作业
        db.delete(assignment)
    
    # 删除课程
    db.delete(course)
    db.commit()
    
    return RedirectResponse(url="/courses", status_code=303) 