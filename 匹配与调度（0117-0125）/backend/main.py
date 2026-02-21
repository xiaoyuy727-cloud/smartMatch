import logging
import traceback

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, UploadFile, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database import engine, get_db
from models import Base, Student, Volunteer
from import_service import parse_excel, preview_import
from schemas import StudentOut, VolunteerOut

app = FastAPI(title="Volunteer-Student MVP")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
    expose_headers=["*"],  # 暴露所有头
)

@app.middleware("http")
async def add_cors_header(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# 启动时建表（MVP）
Base.metadata.create_all(bind=engine)

# MVP：内存缓存 preview 结果
# job_id -> {"type": "students"/"volunteers", "strict": bool, "result": preview_result}
PREVIEW_CACHE = {}

@app.get("/")
def root():
    return {
        "message": "Server is running",
        "docs": "http://127.0.0.1:8000/docs",
        "students": "GET /api/students",
        "volunteers": "GET /api/volunteers",
        "students_import": "POST /api/students/import/preview",
        "volunteers_import": "POST /api/volunteers/import/preview",
    }

def _new_job_id():
    return f"job_{len(PREVIEW_CACHE) + 1}"

# -------------------------------------------------------------------
# Students Import (split routes)
# -------------------------------------------------------------------

@app.post("/api/students/import/preview")
async def students_import_preview(
    file: UploadFile,
    strict: bool = True,
    max_preview_rows: int = 50
):
    df = parse_excel(file.file)
    result = preview_import(df, "students", max_preview_rows=max_preview_rows)

    if "fatal_error" in result:
        raise HTTPException(status_code=400, detail=result["fatal_error"])

    job_id = _new_job_id()
    PREVIEW_CACHE[job_id] = {"type": "students", "strict": strict, "result": result}

    return {
        "job_id": job_id,
        "type": "students",
        "strict": strict,
        "status": "preview_ready",
        "stats": result["stats"],
        "columns": result["columns"],
        "preview": result["preview"],
        "error_summary": result["error_summary"],
    }


@app.post("/api/students/import/{job_id}/commit")
async def students_import_commit(
    job_id: str,
    db: Session = Depends(get_db)
):
    """提交学生数据 - 重复的不导入，不重复的导入"""
    job = PREVIEW_CACHE.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["type"] != "students":
        raise HTTPException(400, "job type mismatch")

    result = job["result"]
    strict = job["strict"]

    if strict and result["stats"]["error_rows"] > 0:
        raise HTTPException(status_code=409, detail={
            "code": "VALIDATION_FAILED",
            "message": f"存在 {result['stats']['error_rows']} 行错误，严格模式下禁止提交"
        })

    # 从 result 中获取数据
    if "rows_cleaned" in result:
        rows_cleaned = result["rows_cleaned"]
        errors_by_row = result.get("errors_by_row", [])
    elif "all_rows" in result:
        all_rows = result["all_rows"]
        rows_cleaned = [r["data"] for r in all_rows]
        errors_by_row = [{"row_index": i+2, "errors": r["errors"]} for i, r in enumerate(all_rows) if r["errors"]]
    else:
        rows_cleaned = result.get("preview", [])
        errors_by_row = result.get("error_summary", [])

    error_indices = {e["row_index"] for e in errors_by_row}
    
    # 筛选出有效数据
    valid_rows = []
    for idx, row in enumerate(rows_cleaned):
        if (idx + 2) not in error_indices:
            valid_rows.append(row)

    print(f"找到 {len(valid_rows)} 条有效学生数据")

    # 区分新数据和已存在数据
    to_insert = []
    conflicts = []
    
    for d in valid_rows:
        exists = db.get(Student, d["seq_no"])
        if exists:
            conflicts.append({
                "seq_no": d["seq_no"],
                "name": d["name"],
                "existing_name": exists.name
            })
            print(f"跳过已存在的学生: {d['seq_no']} - {d['name']}")
        else:
            to_insert.append(d)
            print(f"准备插入新学生: {d['seq_no']} - {d['name']}")

    # 插入新数据
    objs = []
    for d in to_insert:
        try:
            obj = Student(
                seq_no=str(d["seq_no"]),
                name=d["name"],
                gender=d["gender"],
                grade_stage=int(d["grade_stage"]),
                mode=d["mode"],
                subj1=str(d.get("subj1", "")),
                subj2=str(d.get("subj2", "")),
                subj3=str(d.get("subj3", "")),
                weakness_text=d.get("weakness_text"),
                learning_style=d.get("learning_style"),
                interests_text=d.get("interests_text"),
                personality_text=d.get("personality_text"),
                social_worker_name=d.get("social_worker_name"),
                social_worker_phone=d.get("social_worker_phone"),
                is_priority=bool(d.get("is_priority", False)),
                special_needs_text=d.get("special_needs_text"),
            )
            objs.append(obj)
        except Exception as e:
            print(f"创建学生对象失败: {e}")
            continue
    
    inserted_count = 0
    if objs:
        try:
            db.add_all(objs)
            db.commit()
            inserted_count = len(objs)
            print(f"成功插入 {inserted_count} 条新学生数据")
        except Exception as e:
            print(f"数据库插入失败: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"数据库插入失败: {str(e)}")
    
    return {
        "job_id": job_id,
        "status": "committed",
        "inserted": inserted_count,
        "skipped": len(conflicts),
        "total_valid": len(valid_rows),
        "message": f"成功导入 {inserted_count} 条，跳过 {len(conflicts)} 条已存在的记录"
    }

# -------------------------------------------------------------------
# Volunteers Import (split routes)
# -------------------------------------------------------------------

@app.post("/api/volunteers/import/preview")
async def volunteers_import_preview(
    file: UploadFile,
    strict: bool = True,
    max_preview_rows: int = 50
):
    df = parse_excel(file.file)
    result = preview_import(df, "volunteers", max_preview_rows=max_preview_rows)

    if "fatal_error" in result:
        raise HTTPException(status_code=400, detail=result["fatal_error"])

    job_id = _new_job_id()
    PREVIEW_CACHE[job_id] = {"type": "volunteers", "strict": strict, "result": result}

    return {
        "job_id": job_id,
        "type": "volunteers",
        "strict": strict,
        "status": "preview_ready",
        "stats": result["stats"],
        "columns": result["columns"],
        "preview": result["preview"],
        "error_summary": result["error_summary"],
    }


@app.post("/api/volunteers/import/{job_id}/commit")
async def volunteers_import_commit(
    job_id: str,
    db: Session = Depends(get_db)
):
    """提交志愿者数据 - 重复的不导入，不重复的导入"""
    job = PREVIEW_CACHE.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["type"] != "volunteers":
        raise HTTPException(400, "job type mismatch")

    result = job["result"]
    strict = job["strict"]

    if strict and result["stats"]["error_rows"] > 0:
        raise HTTPException(status_code=409, detail={
            "code": "VALIDATION_FAILED",
            "message": f"存在 {result['stats']['error_rows']} 行错误，严格模式下禁止提交"
        })

    # 从 result 中获取数据
    if "rows_cleaned" in result:
        rows_cleaned = result["rows_cleaned"]
        errors_by_row = result.get("errors_by_row", [])
    elif "all_rows" in result:
        all_rows = result["all_rows"]
        rows_cleaned = [r["data"] for r in all_rows]
        errors_by_row = [{"row_index": i+2, "errors": r["errors"]} for i, r in enumerate(all_rows) if r["errors"]]
    elif "preview" in result:
        rows_cleaned = result["preview"]
        errors_by_row = result.get("error_summary", [])
    else:
        print(f"result 中的键: {result.keys()}")
        raise HTTPException(status_code=500, detail=f"无法识别的数据结构: {list(result.keys())}")

    error_indices = {e["row_index"] for e in errors_by_row}
    
    # 筛选出有效数据（没有错误的行）
    valid_rows = []
    for idx, row in enumerate(rows_cleaned):
        if (idx + 2) not in error_indices:
            valid_rows.append(row)

    print(f"找到 {len(valid_rows)} 条有效数据")

    # 分别记录：要插入的、冲突的、重复的
    to_insert = []
    conflicts = []
    existing_records = []
    
    for d in valid_rows:
        exists = db.get(Volunteer, d["seq_no"])
        if exists:
            # 记录冲突信息
            conflicts.append({
                "seq_no": d["seq_no"],
                "name": d["name"],
                "existing_name": exists.name
            })
            existing_records.append(d)
            print(f"跳过已存在的志愿者: {d['seq_no']} - {d['name']}")
        else:
            to_insert.append(d)
            print(f"准备插入新志愿者: {d['seq_no']} - {d['name']}")

    # 插入不重复的数据
    objs = []
    for d in to_insert:
        try:
            obj = Volunteer(
                seq_no=str(d["seq_no"]),
                name=d["name"],
                gender=d["gender"],
                student_no=d.get("student_no"),
                email=d.get("email"),
                department_major=d.get("department_major"),
                mode=d["mode"],
                match_mode=d["match_mode"],
                gender_requirement=d.get("gender_requirement", "none"),
                grade1=int(d.get("grade1", 0) or 0),
                grade2=int(d.get("grade2", 0) or 0),
                grade3=int(d.get("grade3", 0) or 0),
                subj1=str(d.get("subj1", "")),
                subj2=str(d.get("subj2", "")),
                subj3=str(d.get("subj3", "")),
                capacity=int(d.get("capacity", 1) or 1),
                teaching_style_text=d.get("teaching_style_text", d.get("style_text", "")),
                participated_before=bool(d.get("participated_before", d.get("has_participated_before", False))),
            )
            objs.append(obj)
            print(f"成功创建志愿者对象: {obj.seq_no}")
            
        except Exception as e:
            print(f"创建志愿者对象失败: {e}")
            traceback.print_exc()
            continue
    
    # 批量插入
    inserted_count = 0
    if objs:
        try:
            db.add_all(objs)
            db.commit()
            inserted_count = len(objs)
            print(f"成功插入 {inserted_count} 条新志愿者数据")
        except Exception as e:
            print(f"数据库插入失败: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"数据库插入失败: {str(e)}")
    
    # 返回详细的结果信息
    return {
        "job_id": job_id,
        "status": "committed",
        "inserted": inserted_count,
        "skipped": len(conflicts),
        "total_valid": len(valid_rows),
        "details": {
            "inserted": inserted_count,
            "skipped_count": len(conflicts),
            "skipped_items": conflicts[:10],  # 只返回前10条冲突记录，避免响应过大
        },
        "message": f"成功导入 {inserted_count} 条，跳过 {len(conflicts)} 条已存在的记录"
    }

# -------------------------------------------------------------------
# List APIs: pagination + simple filters
# -------------------------------------------------------------------

@app.get("/api/students")
def list_students(
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = Query(20, ge=1, le=200),
    grade_stage: int | None = Query(None, description="1/2/3"),
    mode: str | None = Query(None, description="online/offline/both"),
    is_priority: int | None = Query(None, description="0/1"),
    q: str | None = Query(None, description="姓名模糊搜索"),
):
    stmt = select(Student)
    count_stmt = select(func.count()).select_from(Student)

    if grade_stage is not None:
        stmt = stmt.where(Student.grade_stage == grade_stage)
        count_stmt = count_stmt.where(Student.grade_stage == grade_stage)

    if mode is not None:
        stmt = stmt.where(Student.mode == mode)
        count_stmt = count_stmt.where(Student.mode == mode)

    if is_priority is not None:
        stmt = stmt.where(Student.is_priority == bool(is_priority))
        count_stmt = count_stmt.where(Student.is_priority == bool(is_priority))

    if q:
        like = f"%{q}%"
        stmt = stmt.where(Student.name.like(like))
        count_stmt = count_stmt.where(Student.name.like(like))

    total = db.execute(count_stmt).scalar_one()
    items = db.execute(stmt.order_by(Student.seq_no).offset(offset).limit(limit)).scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [StudentOut.model_validate(i) for i in items],
    }


@app.get("/api/volunteers")
def list_volunteers(
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = Query(20, ge=1, le=200),
    match_mode: str | None = Query(None, description="direct/pre"),
    mode: str | None = Query(None, description="online/offline/both"),
    department_q: str | None = Query(None, description="院系/专业模糊搜索"),
    q: str | None = Query(None, description="姓名模糊搜索"),
):
    stmt = select(Volunteer)
    count_stmt = select(func.count()).select_from(Volunteer)

    if match_mode is not None:
        stmt = stmt.where(Volunteer.match_mode == match_mode)
        count_stmt = count_stmt.where(Volunteer.match_mode == match_mode)

    if mode is not None:
        stmt = stmt.where(Volunteer.mode == mode)
        count_stmt = count_stmt.where(Volunteer.mode == mode)

    if department_q:
        like = f"%{department_q}%"
        stmt = stmt.where(Volunteer.department_major.like(like))
        count_stmt = count_stmt.where(Volunteer.department_major.like(like))

    if q:
        like = f"%{q}%"
        stmt = stmt.where(Volunteer.name.like(like))
        count_stmt = count_stmt.where(Volunteer.name.like(like))

    total = db.execute(count_stmt).scalar_one()
    items = db.execute(stmt.order_by(Volunteer.seq_no).offset(offset).limit(limit)).scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [VolunteerOut.model_validate(i) for i in items],
    }

# 删除单个志愿者
@app.delete("/api/volunteers/{seq_no}")
async def delete_volunteer(seq_no: str, db: Session = Depends(get_db)):
    volunteer = db.get(Volunteer, seq_no)
    if not volunteer:
        raise HTTPException(404, "志愿者不存在")
    db.delete(volunteer)
    db.commit()
    return {"message": "删除成功"}

# 删除单个学生
@app.delete("/api/students/{seq_no}")
async def delete_student(seq_no: str, db: Session = Depends(get_db)):
    student = db.get(Student, seq_no)
    if not student:
        raise HTTPException(404, "学生不存在")
    db.delete(student)
    db.commit()
    return {"message": "删除成功"}

