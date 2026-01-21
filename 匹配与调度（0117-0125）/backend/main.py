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
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def students_import_commit(job_id: str, db: Session = Depends(get_db)):
    job = PREVIEW_CACHE.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["type"] != "students":
        raise HTTPException(400, "job type mismatch: this job is not students")

    result = job["result"]
    strict = job["strict"]

    if strict and result["stats"]["error_rows"] > 0:
        raise HTTPException(status_code=409, detail={
            "code": "VALIDATION_FAILED",
            "message": "存在硬错误，严格模式下禁止提交",
            "error_rows": result["stats"]["error_rows"]
        })

    rows = result["all_rows"]
    to_insert = [r["data"] for r in rows if len(r["errors"]) == 0]

    # on_conflict = reject（不改）
    for d in to_insert:
        exists = db.get(Student, d["seq_no"])
        if exists:
            raise HTTPException(status_code=409, detail={
                "code": "PK_CONFLICT",
                "message": f"students.seq_no={d['seq_no']} 已存在，拒绝导入（reject）"
            })

    objs = [
        Student(
            seq_no=d["seq_no"],
            name=d["name"],
            gender=d["gender"],
            grade_stage=d["grade_stage"],
            mode=d["mode"],
            subj1=d["subj1"], subj2=d["subj2"], subj3=d["subj3"],
            weakness_text=d.get("weakness_text"),
            learning_style=d.get("learning_style"),
            interests_text=d.get("interests_text"),
            personality_text=d.get("personality_text"),
            social_worker_name=d["social_worker_name"],
            social_worker_phone=d["social_worker_phone"],
            is_priority=bool(d["is_priority"]),
            special_needs_text=d.get("special_needs_text"),
        )
        for d in to_insert
    ]
    db.add_all(objs)
    db.commit()
    return {"job_id": job_id, "status": "committed", "inserted": len(objs)}

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
async def volunteers_import_commit(job_id: str, db: Session = Depends(get_db)):
    job = PREVIEW_CACHE.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["type"] != "volunteers":
        raise HTTPException(400, "job type mismatch: this job is not volunteers")

    result = job["result"]
    strict = job["strict"]

    if strict and result["stats"]["error_rows"] > 0:
        raise HTTPException(status_code=409, detail={
            "code": "VALIDATION_FAILED",
            "message": "存在硬错误，严格模式下禁止提交",
            "error_rows": result["stats"]["error_rows"]
        })

    rows = result["all_rows"]
    to_insert = [r["data"] for r in rows if len(r["errors"]) == 0]

    # on_conflict = reject（不改）
    for d in to_insert:
        exists = db.get(Volunteer, d["seq_no"])
        if exists:
            raise HTTPException(status_code=409, detail={
                "code": "PK_CONFLICT",
                "message": f"volunteers.seq_no={d['seq_no']} 已存在，拒绝导入（reject）"
            })

    objs = [
        Volunteer(
            seq_no=d["seq_no"],
            name=d["name"],
            gender=d["gender"],
            student_no=d["student_no"],
            email=d["email"],
            department_major=d["department_major"],
            mode=d["mode"],
            match_mode=d["match_mode"],
            has_participated_before=bool(d["has_participated_before"]),
            style_text=d.get("style_text"),
            gender_requirement=d["gender_requirement"],
            subj1=d["subj1"], subj2=d["subj2"], subj3=d["subj3"],
            grade1=d["grade1"], grade2=d["grade2"], grade3=d["grade3"],
            capacity=int(d["capacity"]),
        )
        for d in to_insert
    ]
    db.add_all(objs)
    db.commit()
    return {"job_id": job_id, "status": "committed", "inserted": len(objs)}

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
