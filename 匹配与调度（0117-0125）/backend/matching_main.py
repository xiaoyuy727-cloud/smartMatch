from fastapi import FastAPI, UploadFile, File, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Student, Volunteer
from import_service import preview_students, preview_volunteers
from schemas import (
    ImportPreviewResponse,
    ImportCommitResponse,
    StudentsListItem,
    VolunteersListItem,
)
from matching_service import preview_topk, run_match_v1
from matching_schemas import MatchPreviewOut, MatchRunOut, CandidatePairOut, MatchPairOut

app = FastAPI(title="Volunteer-Student MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# 内存缓存：job_id -> preview result
PREVIEW_CACHE_STU = {}
PREVIEW_CACHE_VOL = {}


def _err(code: str, message: str, http_status: int = 400):
    raise HTTPException(status_code=http_status, detail={"code": code, "message": message})


# -------------------------
# Students: import preview/commit + list
# -------------------------
@app.post("/api/students/import/preview", response_model=ImportPreviewResponse)
async def students_import_preview(
    file: UploadFile = File(...),
    strict: bool = Query(True),
    max_preview_rows: int = Query(50, ge=1, le=200),
):
    content = await file.read()
    result, err = preview_students(content, strict=strict, max_preview_rows=max_preview_rows)
    if err:
        _err(err["code"], err["message"], 400)

    job_id = result["job_id"]
    PREVIEW_CACHE_STU[job_id] = result

    return {
        "job_id": job_id,
        "stats": result["stats"],
        "error_summary": result["error_summary"],
        "preview": result["preview"],
    }


@app.post("/api/students/import/{job_id}/commit", response_model=ImportCommitResponse)
def students_import_commit(job_id: str, db: Session = Depends(get_db)):
    job = PREVIEW_CACHE_STU.get(job_id)
    if not job:
        _err("JOB_NOT_FOUND", "job_id 不存在（可能服务重启或过期）", 404)

    strict = bool(job.get("strict", True))
    errors = job.get("errors_by_row", [])
    if strict and errors:
        _err("STRICT_REJECT", "存在错误行，strict=true 禁止提交", 409)

    rows = job["rows_cleaned"]
    inserted = 0

    for r in rows:
        if any(e["row_index"] == r.get("_row_index") for e in errors):
            continue

        # 主键冲突检查
        exists = db.get(Student, r["seq_no"])
        if exists:
            _err("PK_CONFLICT", f"students.seq_no={r['seq_no']} 已存在，拒绝导入 (reject)", 409)

        db.add(Student(**r))
        inserted += 1

    db.commit()
    return {"job_id": job_id, "inserted": inserted}


@app.get("/api/students", response_model=dict)
def list_students(
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    q: str | None = Query(None),
    grade_stage: int | None = Query(None),
    mode: str | None = Query(None),
    is_priority: int | None = Query(None),  # 0/1
):
    query = db.query(Student)
    if q:
        query = query.filter(Student.name.contains(q))
    if grade_stage:
        query = query.filter(Student.grade_stage == grade_stage)
    if mode:
        query = query.filter(Student.mode == mode)
    if is_priority in (0, 1):
        query = query.filter(Student.is_priority == (is_priority == 1))

    total = query.count()
    items = (
        query.order_by(Student.seq_no.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [StudentsListItem.model_validate(x.__dict__) for x in items],
    }


# -------------------------
# Volunteers: import preview/commit + list
# -------------------------
@app.post("/api/volunteers/import/preview", response_model=ImportPreviewResponse)
async def volunteers_import_preview(
    file: UploadFile = File(...),
    strict: bool = Query(True),
    max_preview_rows: int = Query(50, ge=1, le=200),
):
    content = await file.read()
    result, err = preview_volunteers(content, strict=strict, max_preview_rows=max_preview_rows)
    if err:
        _err(err["code"], err["message"], 400)

    job_id = result["job_id"]
    PREVIEW_CACHE_VOL[job_id] = result

    return {
        "job_id": job_id,
        "stats": result["stats"],
        "error_summary": result["error_summary"],
        "preview": result["preview"],
    }


@app.post("/api/volunteers/import/{job_id}/commit", response_model=ImportCommitResponse)
def volunteers_import_commit(job_id: str, db: Session = Depends(get_db)):
    job = PREVIEW_CACHE_VOL.get(job_id)
    if not job:
        _err("JOB_NOT_FOUND", "job_id 不存在（可能服务重启或过期）", 404)

    strict = bool(job.get("strict", True))
    errors = job.get("errors_by_row", [])
    if strict and errors:
        _err("STRICT_REJECT", "存在错误行，strict=true 禁止提交", 409)

    rows = job["rows_cleaned"]
    inserted = 0

    for r in rows:
        exists = db.get(Volunteer, r["seq_no"])
        if exists:
            _err("PK_CONFLICT", f"volunteers.seq_no={r['seq_no']} 已存在，拒绝导入 (reject)", 409)

        db.add(Volunteer(**r))
        inserted += 1

    db.commit()
    return {"job_id": job_id, "inserted": inserted}


@app.get("/api/volunteers", response_model=dict)
def list_volunteers(
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    q: str | None = Query(None),
    department_q: str | None = Query(None),
    match_mode: str | None = Query(None),  # direct/pre
    mode: str | None = Query(None),
):
    query = db.query(Volunteer)
    if q:
        query = query.filter(Volunteer.name.contains(q))
    if department_q:
        query = query.filter(Volunteer.department_major.contains(department_q))
    if match_mode:
        query = query.filter(Volunteer.match_mode == match_mode)
    if mode:
        query = query.filter(Volunteer.mode == mode)

    total = query.count()
    items = (
        query.order_by(Volunteer.seq_no.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [VolunteersListItem.model_validate(x.__dict__) for x in items],
    }


# -------------------------
# Match V1: preview + run
# -------------------------
@app.post("/api/match/v1/preview", response_model=MatchPreviewOut)
def match_v1_preview(
    db: Session = Depends(get_db),
    topk: int = Query(200, ge=1, le=2000),
    match_mode: str | None = Query(None),  # direct/pre/None
):
    data = preview_topk(db=db, topk=topk, match_mode=match_mode)

    out = []
    for c in data["topk"]:
        s = c["student"]
        v = c["volunteer"]
        sc = c["score"]
        out.append(
            CandidatePairOut(
                student_seq_no=s["seq_no"],
                student_name=s["name"],
                student_is_priority=bool(s["is_priority"]),
                volunteer_seq_no=v["seq_no"],
                volunteer_name=v["name"],
                volunteer_match_mode=v["match_mode"],
                volunteer_capacity=int(v["capacity"]),
                is_legal=True,
                illegal_reason=None,
                grade_score=sc["grade_score"],
                subject_score=sc["subject_score"],
                style_score=sc["style_score"],
                base_score=sc["base_score"],
                special_penalty=sc["special_penalty"],
                total_score=sc["total_score"],
                best_subject_raw=sc["best_subject_raw"],
                best_subject_ids=sc["best_subject_ids"],
                best_subject_details=sc["best_subject_details"],
            )
        )

    return MatchPreviewOut(total_candidates=data["total_candidates"], topk=out)


@app.post("/api/match/v1/run", response_model=MatchRunOut)
def match_v1_run(
    db: Session = Depends(get_db),
    match_mode: str | None = Query(None),  # direct/pre/None
):
    data = run_match_v1(db=db, match_mode=match_mode)

    matches_out = []
    for c in data["matches"]:
        s = c["student"]
        v = c["volunteer"]
        sc = c["score"]
        matches_out.append(
            MatchPairOut(
                student_seq_no=s["seq_no"],
                student_name=s["name"],
                volunteer_seq_no=v["seq_no"],
                volunteer_name=v["name"],
                total_score=sc["total_score"],
                base_score=sc["base_score"],
                grade_score=sc["grade_score"],
                subject_score=sc["subject_score"],
                style_score=sc["style_score"],
                special_penalty=sc["special_penalty"],
                best_subject_raw=sc["best_subject_raw"],
                best_subject_ids=sc["best_subject_ids"],
                best_subject_details=sc["best_subject_details"],
            )
        )

    return MatchRunOut(
        matches=matches_out,
        unmatched_students=data["unmatched_students"],
        unmatched_volunteers=data["unmatched_volunteers"],
    )
