import os
import uuid
import zipfile
import io
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File as FastAPIFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Assignment, Class, Course, Submission, File as FileModel
from app.schemas import Assignment as AssignmentSchema, AssignmentCreate
from app.auth import get_current_user, teacher_required
from app.templates import templates

router = APIRouter()

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
    # 管理员可以查看所有作业
    if current_user.role == "admin":
        assignments = db.query(Assignment).all()
    else:
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
    # 管理员可以查看所有班级和课程
    if current_user.role == "admin":
        classes = db.query(Class).all()
        courses = db.query(Course).all()
    else:
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
    allowed_file_types: List[str] = Form([".pdf", ".docx"]),  # 默认允许PDF和Word文档
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 确保班级和课程存在
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not class_obj or not course:
        raise HTTPException(status_code=404, detail="班级或课程不存在")
    
    # 管理员可以使用任何班级和课程，教师只能使用自己的
    if current_user.role != "admin":
        # 确保班级和课程属于当前用户
        if class_obj.teacher_id != current_user.id or course.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此班级或课程")
    
    # 确保班级和课程相关联
    if course not in class_obj.courses:
        raise HTTPException(status_code=400, detail="所选班级和课程不相关联")
    
    # 格式化截止日期
    due_date_datetime = datetime.fromisoformat(due_date)
    
    # 格式化允许的文件类型为逗号分隔的字符串
    if not allowed_file_types:
        allowed_file_types = [".pdf", ".docx"]  # 如果没有选择，默认为PDF和Word文档
    
    allowed_file_types_str = ",".join(allowed_file_types)
    
    # 创建新作业
    new_assignment = Assignment(
        title=title,
        description=description,
        class_id=class_id,
        course_id=course_id,
        teacher_id=current_user.id,
        due_date=due_date_datetime,
        allowed_file_types=allowed_file_types_str
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
        
        # 管理员可以查看所有班级和课程
        if current_user.role == "admin":
            classes = db.query(Class).all()
            courses = db.query(Course).all()
        else:
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
    allowed_file_types: List[str] = Form([".pdf", ".docx"]),  # 默认允许PDF和Word文档
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    # 确保只有作业的创建者可以更新
    if assignment.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此作业")
    
    # 确保班级和课程存在
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    course = db.query(Course).filter(Course.id == course_id).first()
    
    if not class_obj or not course:
        raise HTTPException(status_code=404, detail="班级或课程不存在")
    
    # 如果不是管理员，确保班级和课程属于当前用户
    if current_user.role != "admin":
        if class_obj.teacher_id != current_user.id or course.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此班级或课程")
    
    # 确保班级和课程相关联
    if course not in class_obj.courses:
        raise HTTPException(status_code=400, detail="所选班级和课程不相关联")
    
    # 格式化截止日期
    due_date_datetime = datetime.fromisoformat(due_date)
    
    # 格式化允许的文件类型为逗号分隔的字符串
    if not allowed_file_types:
        allowed_file_types = [".pdf", ".docx"]  # 如果没有选择，默认为PDF和Word文档
    
    allowed_file_types_str = ",".join(allowed_file_types)
    
    # 更新作业信息
    assignment.title = title
    assignment.description = description
    assignment.class_id = class_id
    assignment.course_id = course_id
    assignment.due_date = due_date_datetime
    assignment.allowed_file_types = allowed_file_types_str
    
    db.commit()
    
    return RedirectResponse(url=f"/assignments/{assignment_id}", status_code=303)

@router.post("/assignments/{assignment_id}/upload", name="upload_assignment")
async def upload_file(
    assignment_id: int,
    files: List[UploadFile] = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 检查学生是否有权上传
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="作业不存在")
        
        if current_user.role != "student":
            raise HTTPException(status_code=403, detail="只有学生才能提交作业")
        
        # 确保学生属于这个班级
        if current_user not in assignment.class_obj.students:
            raise HTTPException(status_code=403, detail="无权提交此作业")
        
        # 检查是否超过截止日期
        current_time = datetime.now()
        if current_time > assignment.due_date:
            raise HTTPException(status_code=403, detail="已超过截止日期，无法提交")
        
        # 获取允许的文件类型列表
        allowed_extensions = assignment.allowed_file_types.split(',') if assignment.allowed_file_types else [".pdf", ".docx"]
        
        # 获取文件大小限制（以字节为单位）
        max_file_size_bytes = (assignment.max_file_size if assignment.max_file_size else 5) * 1024 * 1024  # 转换为字节
        
        # 验证文件类型和大小
        for file in files:
            filename = file.filename.lower()
            file_ext = os.path.splitext(filename)[1]
            
            # 检查文件类型
            if file_ext not in allowed_extensions:
                allowed_types_formatted = ", ".join(allowed_extensions)
                raise HTTPException(
                    status_code=400, 
                    detail=f"不支持的文件类型: {file_ext}。此作业只允许上传以下类型的文件: {allowed_types_formatted}"
                )
            
            # 检查文件大小
            # 读取文件内容来获取确切大小
            file_content = await file.read()
            if len(file_content) > max_file_size_bytes:
                # 重置文件指针，以便后续操作可以再次读取文件
                await file.seek(0)
                raise HTTPException(
                    status_code=400,
                    detail=f"文件 {file.filename} 大小超过限制。最大允许大小: {assignment.max_file_size if assignment.max_file_size else 5} MB"
                )
            
            # 重置文件指针，以便后续操作可以再次读取文件
            await file.seek(0)
        
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
    
    except HTTPException as e:
        # 直接重新抛出HTTP异常，让全局异常处理器处理
        raise
    
    except Exception as e:
        # 处理其他未预期的异常
        print(f"文件上传时发生错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"文件上传失败: {str(e)}"
        )

@router.get("/files/{file_id}/download", name="download_file")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
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
            raise HTTPException(status_code=404, detail="文件不存在或已被删除")
        
        # 使用 FileResponse，它会自动处理文件传输，并支持大文件
        return FileResponse(
            path=file_path, 
            filename=file.filename,
            media_type=file.filetype or "application/octet-stream"
        )
    except Exception as e:
        print(f"下载单个文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件时出错: {str(e)}")

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

@router.get("/assignments/{assignment_id}/download-all", name="download_all_files")
async def download_all_files(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 检查作业是否存在
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    # 检查是否有权限下载
    if current_user.role == "student":
        raise HTTPException(status_code=403, detail="学生无权批量下载作业文件")
    
    if current_user.role == "teacher" and assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有作业创建者才能批量下载文件")
    
    try:
        # 获取所有提交
        submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
        
        # 确保uploads目录存在
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 创建内存中的zip文件
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 检查是否有文件可供下载
            has_files = False
            
            for submission in submissions:
                # 获取学生信息
                student = submission.student
                student_folder = f"{student.username}_{student.id}"
                
                for file in submission.files:
                    # 获取文件实际路径
                    file_path = os.path.join(UPLOAD_DIR, file.filepath)
                    if os.path.exists(file_path):
                        try:
                            # 在zip中创建以学生命名的文件夹
                            # 确保文件名编码正确
                            zip_path = os.path.join(student_folder, file.filename)
                            # 添加文件到zip
                            zip_file.write(file_path, zip_path)
                            has_files = True
                        except Exception as e:
                            print(f"添加文件到ZIP时出错: {str(e)}")
                            continue
            
            # 如果没有找到任何文件
            if not has_files:
                raise HTTPException(status_code=404, detail="没有找到可下载的文件")
        
        # 将指针重置到开始位置
        zip_buffer.seek(0)
        
        # 生成下载文件名 - 使用ASCII文件名以避免编码问题
        safe_title = ''.join(c if c.isalnum() else '_' for c in assignment.title)
        zip_filename = f"assignment_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        
        # 返回流式响应
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"'
            }
        )
    except Exception as e:
        print(f"下载文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载文件时出错: {str(e)}")

@router.get("/submissions/{submission_id}/download-all", name="download_submission_files")
async def download_submission_files(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 检查提交是否存在
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    
    # 检查是否有权限下载
    if current_user.role == "student" and submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权下载此文件")
    
    if current_user.role == "teacher" and submission.assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权下载此文件")
    
    try:
        # 获取学生信息
        student = submission.student
        
        # 检查是否有文件
        if not submission.files:
            raise HTTPException(status_code=404, detail="此提交没有文件")
        
        # 确保uploads目录存在
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # 创建内存中的zip文件
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 检查是否有文件可供下载
            has_files = False
            
            for file in submission.files:
                # 获取文件实际路径
                file_path = os.path.join(UPLOAD_DIR, file.filepath)
                if os.path.exists(file_path):
                    try:
                        # 添加文件到zip
                        zip_file.write(file_path, file.filename)
                        has_files = True
                    except Exception as e:
                        print(f"添加文件到ZIP时出错: {str(e)}")
                        continue
            
            # 如果没有找到任何文件
            if not has_files:
                raise HTTPException(status_code=404, detail="没有找到可下载的文件")
        
        # 将指针重置到开始位置
        zip_buffer.seek(0)
        
        # 生成下载文件名 - 使用ASCII文件名以避免编码问题
        safe_username = ''.join(c if c.isalnum() else '_' for c in student.username)
        safe_title = ''.join(c if c.isalnum() else '_' for c in submission.assignment.title)
        zip_filename = f"{safe_username}_submission_{safe_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        
        # 返回流式响应
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"'
            }
        )
    except Exception as e:
        print(f"下载提交文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载提交文件时出错: {str(e)}")

@router.get("/delete_assignment/{assignment_id}", name="delete_assignment")
async def delete_assignment(
    assignment_id: int,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    """删除作业"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    # 确保只有作业的创建者或管理员可以删除
    if assignment.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权删除此作业")
    
    # 查找相关提交
    submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
    
    # 删除每个提交及其关联文件
    for submission in submissions:
        # 删除文件
        db.query(FileModel).filter(FileModel.submission_id == submission.id).delete()
        # 删除提交
        db.delete(submission)
    
    # 删除作业
    db.delete(assignment)
    db.commit()
    
    return RedirectResponse(url="/assignments", status_code=303) 