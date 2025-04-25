from typing import List
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File as FastAPIFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Class, Course, Assignment, Submission, File
from app.schemas import Class as ClassSchema, ClassCreate, ClassUpdate
from app.auth import get_current_user, get_password_hash, teacher_required, get_token_from_request

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/classes", response_class=HTMLResponse, name="classes")
async def list_classes(
    request: Request,
    page: int = 1,
    per_page: int = 8,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 构建基础查询
    if current_user.role == "admin":
        base_query = db.query(Class)
    else:
        base_query = db.query(Class).filter(Class.teacher_id == current_user.id)
    
    # 计算总数和总页数
    total = base_query.count()
    total_pages = (total + per_page - 1) // per_page  # 向上取整
    
    # 分页查询
    classes = base_query.order_by(Class.id).offset((page - 1) * per_page).limit(per_page).all()
    
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
    
    # 构建总统计数据
    # 获取所有班级以计算总学生数和总课程数（仅用于统计面板）
    all_classes = base_query.all() if total <= 50 else []  # 只在班级数量合理时进行统计
    
    stats = {
        "total_classes": total,
        "total_students": sum(len(cls.students) for cls in all_classes) if all_classes else None,
        "total_courses": sum(len(cls.courses) for cls in all_classes) if all_classes else None,
    }
    
    return templates.TemplateResponse(
        "classes.html",
        {
            "request": request, 
            "user": current_user, 
            "classes": classes,
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

@router.get("/classes/create", response_class=HTMLResponse, name="create_class")
async def create_class_page(
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 管理员可以查看所有课程，教师只能查看自己创建的课程
    if current_user.role == "admin":
        courses = db.query(Course).all()
    else:
        courses = db.query(Course).filter(Course.teacher_id == current_user.id).all()
    
    return templates.TemplateResponse(
        "class_form.html",
        {
            "request": request, 
            "user": current_user, 
            "courses": courses
        }
    )

@router.post("/classes/create")
async def create_class(
    class_name: str = Form(...),
    description: str = Form(None),
    courses: List[int] = Form([]),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    # 创建新班级
    new_class = Class(
        name=class_name,
        description=description,
        teacher_id=current_user.id
    )
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    
    # 添加关联课程
    if courses:
        for course_id in courses:
            course = db.query(Course).filter(Course.id == course_id).first()
            if course:
                new_class.courses.append(course)
        
        db.commit()
    
    return RedirectResponse(url="/classes", status_code=303)

@router.get("/classes/{class_id}", response_class=HTMLResponse, name="view_class")
async def view_class(
    class_id: int,
    request: Request,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只有班级的创建者可以查看
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问此班级")
    
    # 获取所有可以添加到班级的学生（尚未加入该班级的学生）
    available_students = db.query(User).filter(
        User.role == "student",
        ~User.id.in_([student.id for student in class_obj.students])
    ).all()
    
    return templates.TemplateResponse(
        "class_form.html",
        {
            "request": request, 
            "user": current_user, 
            "class": class_obj,
            "courses": db.query(Course).filter(Course.teacher_id == current_user.id).all(),
            "available_students": available_students
        }
    )

@router.post("/classes/{class_id}/update", name="update_class")
async def update_class(
    class_id: int,
    class_name: str = Form(...),
    description: str = Form(None),
    courses: List[int] = Form([]),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只有班级的创建者可以更新
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此班级")
    
    # 更新班级信息
    class_obj.name = class_name
    class_obj.description = description
    
    # 更新关联课程
    class_obj.courses = []
    if courses:
        for course_id in courses:
            course = db.query(Course).filter(Course.id == course_id).first()
            if course:
                class_obj.courses.append(course)
    
    db.commit()
    
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)

@router.post("/classes/{class_id}/students/add", name="add_student_to_class")
async def add_student_to_class(
    class_id: int,
    student_id: int = Form(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只有班级的创建者可以添加学生
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此班级")
    
    student = db.query(User).filter(User.id == student_id, User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 检查学生是否已在班级中
    if student in class_obj.students:
        raise HTTPException(status_code=400, detail="学生已在班级中")
    
    # 添加学生到班级
    class_obj.students.append(student)
    db.commit()
    
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)

@router.post("/classes/{class_id}/students/{student_id}/remove", name="remove_student_from_class")
async def remove_student_from_class(
    class_id: int,
    student_id: int,
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只有班级的创建者可以移除学生
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此班级")
    
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 移除学生
    if student in class_obj.students:
        class_obj.students.remove(student)
        db.commit()
    
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)

@router.get("/templates/student_template", name="download_student_template")
async def download_student_template():
    """下载学生导入模板"""
    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow(["username", "password", "organization", "id_number"])
    writer.writerow(["student1", "password1", "示例大学", "2023001"])
    writer.writerow(["student2", "password2", "示例大学", "2023002"])
    
    content.seek(0)
    
    return StreamingResponse(
        iter([content.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment;filename=student_template.csv"}
    )

@router.post("/classes/{class_id}/students/import", name="import_students")
async def import_students(
    class_id: int,
    students_file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(teacher_required),
    db: Session = Depends(get_db)
):
    class_obj = db.query(Class).filter(Class.id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")
    
    # 确保只有班级的创建者可以导入学生
    if class_obj.teacher_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改此班级")
    
    # 读取文件内容
    content = await students_file.read()
    
    # 尝试多种编码格式解码
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']
    decoded_content = None
    
    for encoding in encodings:
        try:
            decoded_content = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    
    if decoded_content is None:
        raise HTTPException(
            status_code=400, 
            detail="无法解码文件内容。请确保文件使用UTF-8、GBK、GB2312或GB18030编码。"
        )
    
    try:
        csv_reader = csv.reader(io.StringIO(decoded_content))
        
        # 跳过标题行
        next(csv_reader)
        
        # 导入学生
        for row in csv_reader:
            if len(row) >= 2:
                username, password = row[0], row[1]
                
                # 提取学校和学号信息（如果存在）
                organization = None
                id_number = None
                
                if len(row) >= 3:
                    organization = row[2]
                
                if len(row) >= 4:
                    id_number = row[3]
                
                # 检查学生是否已存在
                student = db.query(User).filter(User.username == username).first()
                if not student:
                    # 创建新学生
                    hashed_password = get_password_hash(password)
                    student = User(
                        username=username,
                        hashed_password=hashed_password,
                        role="student",
                        organization=organization,
                        id_number=id_number
                    )
                    db.add(student)
                    db.commit()
                    db.refresh(student)
                elif student.role == "student":
                    # 如果学生已存在且是学生角色，更新学校和学号信息（仅当CSV中有提供）
                    if organization and not student.organization:
                        student.organization = organization
                    if id_number and not student.id_number:
                        student.id_number = id_number
                    db.commit()
                
                # 检查学生是否已在班级中
                if student not in class_obj.students and student.role == "student":
                    class_obj.students.append(student)
        
        db.commit()
        
        return RedirectResponse(url=f"/classes/{class_id}", status_code=303)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"导入过程中出错: {str(e)}"
        )

@router.get("/delete_class/{class_id}", name="delete_class")
async def delete_class(
    request: Request,
    class_id: int,
    db: Session = Depends(get_db)
):
    """删除班级"""
    # 先验证用户身份
    try:
        token = await get_token_from_request(request)
        if not token:
            return RedirectResponse(url="/login", status_code=303)
        
        current_user = await get_current_user(request, db)
        
        # 确认是管理员或教师
        if current_user.role != "admin" and current_user.role != "teacher":
            raise HTTPException(status_code=403, detail="权限不足，需要教师或管理员权限")
        
        class_obj = db.query(Class).filter(Class.id == class_id).first()
        if not class_obj:
            raise HTTPException(status_code=404, detail="班级不存在")
        
        # 确保只有班级的创建者或管理员可以删除
        if class_obj.teacher_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="无权删除此班级")
        
        # 删除班级前先解除相关关联
        class_obj.courses = []
        class_obj.students = []
        
        # 获取与班级相关的作业
        assignments = db.query(Assignment).filter(Assignment.class_id == class_id).all()
        
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
        
        # 删除班级
        db.delete(class_obj)
        db.commit()
        
        return RedirectResponse(url="/classes", status_code=303)
    
    except HTTPException as e:
        # 重定向到登录页面
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        raise e 