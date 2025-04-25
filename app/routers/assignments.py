import os
import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Assignment, Class, Course, Submission, File as FileModel
from app.schemas import Assignment as AssignmentSchema, AssignmentCreate
from app.auth import get_current_user, teacher_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 设置上传文件保存的目录
UPLOAD_DIR = os.path.join(os.getcwd(), "app", "uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.get("/assignments", response_class=HTMLResponse, name="assignments")
async def list_assignments(
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    assignments = db.query(Assignment).filter(Assignment.teacher_id == current_user.id).all()
    
    # 为每个作业添加提交统计信息
    for assignment in assignments:
        assignment.submissions_count = len(assignment.submissions)
        assignment.total_students = len(assignment.class_obj.students) if assignment.class_obj else 0
    
    return templates.TemplateResponse(
        "assignments.html",
        {"request": request, "user": current_user, "assignments": assignments}
    )

@router.get("/assignments/create", response_class=HTMLResponse, name="create_assignment")
async def create_assignment_page(
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    classes = db.query(Class).filter(Class.teacher_id == current_user.id).all()
    courses = db.query(Course).filter(Course.teacher_id == current_user.id).all()
    
    return templates.TemplateResponse(
        "assignment_form.html",
        {
            "request": request, 
            "user": current_user, 
            "classes": classes,
            "courses": courses
        }
    )

@router.post("/assignments/create", name="create_assignment_post")
async def create_assignment(
    title: str = Form(...),
    description: str = Form(...),
    class_id: int = Form(...),
    course_id: int = Form(...),
    due_date: str = Form(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 确保班级和课程属于当前用户
    class_obj = db.query(Class).filter(Class.id == class_id, Class.teacher_id == current_user.id).first()
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    
    if not class_obj or not course:
        raise HTTPException(status_code=404, detail="班级或课程不存在")
    
    # 确保班级和课程相关联
    if course not in class_obj.courses:
        raise HTTPException(status_code=400, detail="所选班级和课程不相关联")
    
    # 格式化截止日期
    due_date_datetime = datetime.fromisoformat(due_date)
    
    # 创建新作业
    new_assignment = Assignment(
        title=title,
        description=description,
        class_id=class_id,
        course_id=course_id,
        teacher_id=current_user.id,
        due_date=due_date_datetime
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    
    return RedirectResponse(url="/assignments", status_code=303)

@router.get("/assignments/{assignment_id}", response_class=HTMLResponse, name="view_assignment")
async def view_assignment(
    assignment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    # 如果是老师，展示学生提交情况
    if current_user.role == "teacher" or current_user.role == "admin":
        # 确保只有作业的创建者可以查看
        if assignment.teacher_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="无权访问此作业")
        
        # 获取所有提交
        submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
        
        # 创建学生ID到提交的映射，用于模板中的查询
        submissions_by_student = {submission.student_id: submission for submission in submissions}
        
        classes = db.query(Class).filter(Class.teacher_id == current_user.id).all()
        courses = db.query(Course).filter(Course.teacher_id == current_user.id).all()
        
        return templates.TemplateResponse(
            "assignment_form.html",
            {
                "request": request, 
                "user": current_user, 
                "assignment": assignment,
                "classes": classes,
                "courses": courses,
                "submissions": submissions,
                "submissions_by_student": submissions_by_student
            }
        )
    
    # 如果是学生，展示上传界面
    elif current_user.role == "student":
        # 确保学生属于这个班级
        if current_user not in assignment.class_obj.students:
            raise HTTPException(status_code=403, detail="无权访问此作业")
        
        # 检查学生是否已提交作业
        submission = db.query(Submission).filter(
            Submission.assignment_id == assignment_id,
            Submission.student_id == current_user.id
        ).first()
        
        # 标记作业状态
        if submission:
            assignment.status = "submitted"
        else:
            assignment.status = "pending"
        
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request, 
                "user": current_user, 
                "assignment": assignment,
                "submission": submission,
                "now": datetime.now()
            }
        )
    
    # 其他情况
    raise HTTPException(status_code=403, detail="无权访问此页面")

@router.post("/assignments/{assignment_id}/update", name="update_assignment")
async def update_assignment(
    assignment_id: int,
    title: str = Form(...),
    description: str = Form(...),
    class_id: int = Form(...),
    course_id: int = Form(...),
    due_date: str = Form(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    # 确保只有作业的创建者可以更新
    if assignment.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此作业")
    
    # 确保班级和课程属于当前用户
    class_obj = db.query(Class).filter(Class.id == class_id, Class.teacher_id == current_user.id).first()
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == current_user.id).first()
    
    if not class_obj or not course:
        raise HTTPException(status_code=404, detail="班级或课程不存在")
    
    # 确保班级和课程相关联
    if course not in class_obj.courses:
        raise HTTPException(status_code=400, detail="所选班级和课程不相关联")
    
    # 格式化截止日期
    due_date_datetime = datetime.fromisoformat(due_date)
    
    # 更新作业信息
    assignment.title = title
    assignment.description = description
    assignment.class_id = class_id
    assignment.course_id = course_id
    assignment.due_date = due_date_datetime
    
    db.commit()
    
    return RedirectResponse(url=f"/assignments/{assignment_id}", status_code=303)

@router.post("/assignments/{assignment_id}/upload", name="upload_assignment")
async def upload_file(
    assignment_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 检查学生是否有权上传
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="只有学生才能提交作业")
    
    # 确保学生属于这个班级
    if current_user not in assignment.class_obj.students:
        raise HTTPException(status_code=403, detail="无权提交此作业")
    
    # 检查是否已经超过截止日期
    if datetime.now() > assignment.due_date:
        raise HTTPException(status_code=400, detail="已超过截止日期，无法提交")
    
    # 检查是否已有提交，有则更新，无则创建
    submission = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_user.id
    ).first()
    
    if submission:
        # 删除旧文件
        for file in submission.files:
            file_path = os.path.join(UPLOAD_DIR, file.filepath)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # 删除数据库中的文件记录
        db.query(FileModel).filter(FileModel.submission_id == submission.id).delete()
    else:
        # 创建新提交
        submission = Submission(
            assignment_id=assignment_id,
            student_id=current_user.id
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
    
    # 创建学生专属的目录
    student_dir = os.path.join(UPLOAD_DIR, f"student_{current_user.id}")
    if not os.path.exists(student_dir):
        os.makedirs(student_dir)
    
    # 保存文件
    for file in files:
        # 生成唯一的文件名
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(f"student_{current_user.id}", unique_filename)
        abs_file_path = os.path.join(UPLOAD_DIR, file_path)
        
        # 保存文件
        file_content = await file.read()
        with open(abs_file_path, "wb") as f:
            f.write(file_content)
        
        # 保存文件信息到数据库
        file_size = os.path.getsize(abs_file_path)
        file_model = FileModel(
            filename=file.filename,
            filepath=file_path,
            filesize=file_size,
            filetype=file.content_type or "application/octet-stream",
            submission_id=submission.id
        )
        db.add(file_model)
    
    db.commit()
    
    return RedirectResponse(url=f"/assignments/{assignment_id}", status_code=303)

@router.get("/files/{file_id}/download", name="download_file")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 检查是否有权下载
    submission = file.submission
    if current_user.role == "student" and submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权下载此文件")
    
    if current_user.role == "teacher" and submission.assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权下载此文件")
    
    file_path = os.path.join(UPLOAD_DIR, file.filepath)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(path=file_path, filename=file.filename)

@router.get("/submissions/{submission_id}", name="view_submission")
async def view_submission(
    submission_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    
    # 检查是否有权查看
    if current_user.role == "student" and submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此提交")
    
    if current_user.role == "teacher" and submission.assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此提交")
    
    return templates.TemplateResponse(
        "submission.html",
        {
            "request": request, 
            "user": current_user, 
            "submission": submission,
            "assignment": submission.assignment,
            "files": submission.files
        }
    )

@router.get("/my-assignments", response_class=HTMLResponse, name="my_assignments")
async def my_assignments(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="只有学生才能查看此页面")
    
    # 获取学生所在班级的所有作业
    student_classes = current_user.classes
    class_ids = [class_obj.id for class_obj in student_classes]
    
    assignments = db.query(Assignment).filter(Assignment.class_id.in_(class_ids)).all()
    
    # 检查每个作业的提交状态
    for assignment in assignments:
        submission = db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.student_id == current_user.id
        ).first()
        
        if submission:
            assignment.status = "submitted"
        else:
            assignment.status = "pending"
    
    # 分为待完成和已完成的作业
    pending_assignments = [a for a in assignments if a.status == "pending"]
    completed_assignments = [a for a in assignments if a.status == "submitted"]
    
    return templates.TemplateResponse(
        "my_assignments.html",
        {
            "request": request, 
            "user": current_user, 
            "pending_assignments": pending_assignments,
            "completed_assignments": completed_assignments
        }
    ) 