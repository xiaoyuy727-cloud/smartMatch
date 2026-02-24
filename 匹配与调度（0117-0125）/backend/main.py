from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from export_service import build_matching_export_workbook_bytes
from import_service import (
    commit_students,
    commit_volunteers,
    preview_students_xlsx,
    preview_volunteers_xlsx,
)
from matching_orchestrator import MatchingOrchestrator
from matching_schemas import (
    FinalMatchResultOut,
    PairScoreDetailOut,
    RunFullMatchResponse,
    UnmatchedStudentOut,
    UnusedVolunteerOut,
)
from matching_store import MatchingStore
from models import Student, Volunteer
from schemas import (
    DeleteResponse,
    ImportCommitResponse,
    ImportPreviewResponse,
    RootResponse,
)

# 确保模型已加载并创建表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="师生匹配系统后端（重写版-批次3）",
    version="1.0.0-batch3",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 内部工具开发阶段
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 内存预览缓存（commit 前临时保存）
# =========================

PREVIEW_CACHE_TTL_MINUTES = 30
PREVIEW_CACHE: dict[str, dict[str, Any]] = {}


def _cleanup_preview_cache() -> None:
    now = datetime.utcnow()
    expired = []
    for job_id, payload in PREVIEW_CACHE.items():
        created_at = payload.get("created_at")
        if not isinstance(created_at, datetime):
            expired.append(job_id)
            continue
        if now - created_at > timedelta(minutes=PREVIEW_CACHE_TTL_MINUTES):
            expired.append(job_id)
    for job_id in expired:
        PREVIEW_CACHE.pop(job_id, None)


def _save_preview_job(entity: str, preview_result: dict[str, Any]) -> str:
    _cleanup_preview_cache()
    job_id = str(uuid.uuid4())

    valid_rows = preview_result.pop("valid_rows", [])
    preview_response = preview_result

    PREVIEW_CACHE[job_id] = {
        "entity": entity,
        "created_at": datetime.utcnow(),
        "valid_rows": valid_rows,
        "preview_response": preview_response,
    }
    return job_id


def _get_preview_job(job_id: str, expected_entity: str) -> dict[str, Any]:
    _cleanup_preview_cache()
    payload = PREVIEW_CACHE.get(job_id)
    if not payload:
        raise HTTPException(status_code=404, detail="preview job 不存在或已过期")
    if payload.get("entity") != expected_entity:
        raise HTTPException(status_code=400, detail="preview job 类型不匹配")
    return payload


def _pop_preview_job(job_id: str) -> None:
    PREVIEW_CACHE.pop(job_id, None)


# =========================
# 工具函数（序列化）
# =========================

def _student_to_dict(s: Student) -> dict[str, Any]:
    return {
        "id": s.id,
        "seq_no": s.seq_no,
        "name": s.name,
        "gender": s.gender,
        "stage_code": s.stage_code,
        "tutoring_mode": s.tutoring_mode,
        "subj1": s.subj1,
        "subj2": s.subj2,
        "subj3": s.subj3,
        "student_profile": s.student_profile,
        "learning_style": s.learning_style,
        "interests": s.interests,
        "personality": s.personality,
        "social_worker_name": s.social_worker_name,
        "social_worker_phone": s.social_worker_phone,
        "is_priority": s.is_priority,
        "special_need": s.special_need,
        "grade_stage": s.stage_code,
        "mode": s.tutoring_mode,
    }


def _volunteer_to_dict(v: Volunteer) -> dict[str, Any]:
    return {
        "id": v.id,
        "seq_no": v.seq_no,
        "name": v.name,
        "gender": v.gender,
        "student_no": v.student_no,
        "email": v.email,
        "department": v.department,
        "tutoring_mode": v.tutoring_mode,
        "match_mode": v.match_mode,
        "joined_before": v.joined_before,
        "personality": v.personality,
        "student_gender_requirement": v.student_gender_requirement,
        "subj1": v.subj1,
        "subj2": v.subj2,
        "subj3": v.subj3,
        "stage_pref1": v.stage_pref1,
        "stage_pref2": v.stage_pref2,
        "stage_pref3": v.stage_pref3,
        "capacity": v.capacity,
        "mode": v.tutoring_mode,
    }


def _parse_bool_query(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y"}:
        return True
    if v in {"0", "false", "no", "n"}:
        return False
    return None


# =========================
# 根路由 / 健康检查
# =========================

@app.get("/", response_model=RootResponse)
def root():
    return {
        "name": "师生匹配系统后端",
        "status": "ok",
        "version": "1.0.0-batch3",
        "docs": "/docs",
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}


# =========================
# 学生导入：preview / commit
# =========================

@app.post("/api/students/import/preview", response_model=ImportPreviewResponse)
async def students_import_preview(
    file: UploadFile = File(...),
    strict: Optional[str] = Query(default=None, description="兼容旧前端参数，本版本忽略"),
    max_preview_rows: int = Query(default=50, ge=1, le=500),
):
    _ = strict

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        preview_result = preview_students_xlsx(file_bytes, max_preview_rows=max_preview_rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"学生预览失败: {e}") from e

    job_id = _save_preview_job("students", preview_result)

    payload = PREVIEW_CACHE[job_id]["preview_response"].copy()
    payload["job_id"] = job_id
    return payload


@app.post("/api/students/import/{job_id}/commit", response_model=ImportCommitResponse)
async def students_import_commit(
    job_id: str,
    db: Session = Depends(get_db),
):
    payload = _get_preview_job(job_id, "students")
    valid_rows = payload.get("valid_rows", [])

    try:
        result = commit_students(db, valid_rows)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"学生导入提交失败: {e}") from e

    _pop_preview_job(job_id)

    inserted = result["inserted"]
    skipped_existing = result["skipped_existing"]
    total_candidates = result["total_candidates"]

    return {
        "ok": True,
        "entity": "students",
        "job_id": job_id,
        "total_candidates": total_candidates,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "message": f"学生导入完成：候选{total_candidates}条，新增{inserted}条，跳过已存在{skipped_existing}条",
    }


# =========================
# 志愿者导入：preview / commit
# =========================

@app.post("/api/volunteers/import/preview", response_model=ImportPreviewResponse)
async def volunteers_import_preview(
    file: UploadFile = File(...),
    strict: Optional[str] = Query(default=None, description="兼容旧前端参数，本版本忽略"),
    max_preview_rows: int = Query(default=50, ge=1, le=500),
):
    _ = strict

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        preview_result = preview_volunteers_xlsx(file_bytes, max_preview_rows=max_preview_rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"志愿者预览失败: {e}") from e

    job_id = _save_preview_job("volunteers", preview_result)

    payload = PREVIEW_CACHE[job_id]["preview_response"].copy()
    payload["job_id"] = job_id
    return payload


@app.post("/api/volunteers/import/{job_id}/commit", response_model=ImportCommitResponse)
async def volunteers_import_commit(
    job_id: str,
    db: Session = Depends(get_db),
):
    payload = _get_preview_job(job_id, "volunteers")
    valid_rows = payload.get("valid_rows", [])

    try:
        result = commit_volunteers(db, valid_rows)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"志愿者导入提交失败: {e}") from e

    _pop_preview_job(job_id)

    inserted = result["inserted"]
    skipped_existing = result["skipped_existing"]
    total_candidates = result["total_candidates"]

    return {
        "ok": True,
        "entity": "volunteers",
        "job_id": job_id,
        "total_candidates": total_candidates,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "message": f"志愿者导入完成：候选{total_candidates}条，新增{inserted}条，跳过已存在{skipped_existing}条",
    }


# =========================
# 学生列表 / 删除
# =========================

@app.get("/api/students")
def list_students(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    q: Optional[str] = Query(default=None, description="关键词搜索：序号/姓名"),
    grade_stage: Optional[int] = Query(default=None, description="兼容旧前端字段，映射到stage_code"),
    stage_code: Optional[int] = Query(default=None),
    mode: Optional[str] = Query(default=None, description="兼容旧前端字段，映射到tutoring_mode"),
    tutoring_mode: Optional[str] = Query(default=None),
    is_priority: Optional[str] = Query(default=None, description="支持0/1/true/false"),
):
    stmt = select(Student)

    if q:
        qv = q.strip()
        stmt = stmt.where(
            or_(
                Student.seq_no.contains(qv),
                Student.name.contains(qv),
            )
        )

    final_stage = stage_code if stage_code is not None else grade_stage
    if final_stage is not None:
        stmt = stmt.where(Student.stage_code == final_stage)

    final_mode = (tutoring_mode or mode)
    if final_mode:
        stmt = stmt.where(Student.tutoring_mode == final_mode.strip().lower())

    pri = _parse_bool_query(is_priority)
    if pri is not None:
        stmt = stmt.where(Student.is_priority == pri)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(total_stmt) or 0

    rows = db.scalars(
        stmt.order_by(Student.id.desc()).offset(offset).limit(limit)
    ).all()

    items = [_student_to_dict(s) for s in rows]
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@app.delete("/api/students/{seq_no}", response_model=DeleteResponse)
def delete_student(seq_no: str, db: Session = Depends(get_db)):
    obj = db.scalar(select(Student).where(Student.seq_no == seq_no))
    if not obj:
        raise HTTPException(status_code=404, detail="学生不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True, "deleted": 1, "seq_no": seq_no, "entity": "students"}


# =========================
# 志愿者列表 / 删除
# =========================

@app.get("/api/volunteers")
def list_volunteers(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    q: Optional[str] = Query(default=None, description="关键词搜索：序号/姓名/院系"),
    mode: Optional[str] = Query(default=None, description="兼容旧前端字段，映射到tutoring_mode"),
    tutoring_mode: Optional[str] = Query(default=None),
    match_mode: Optional[str] = Query(default=None),
    joined_before: Optional[str] = Query(default=None, description="支持0/1/true/false"),
):
    stmt = select(Volunteer)

    if q:
        qv = q.strip()
        stmt = stmt.where(
            or_(
                Volunteer.seq_no.contains(qv),
                Volunteer.name.contains(qv),
                Volunteer.department.contains(qv),
            )
        )

    final_mode = (tutoring_mode or mode)
    if final_mode:
        stmt = stmt.where(Volunteer.tutoring_mode == final_mode.strip().lower())

    if match_mode:
        stmt = stmt.where(Volunteer.match_mode == match_mode.strip().lower())

    jb = _parse_bool_query(joined_before)
    if jb is not None:
        stmt = stmt.where(Volunteer.joined_before == jb)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(total_stmt) or 0

    rows = db.scalars(
        stmt.order_by(Volunteer.id.desc()).offset(offset).limit(limit)
    ).all()

    items = [_volunteer_to_dict(v) for v in rows]
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@app.delete("/api/volunteers/{seq_no}", response_model=DeleteResponse)
def delete_volunteer(seq_no: str, db: Session = Depends(get_db)):
    obj = db.scalar(select(Volunteer).where(Volunteer.seq_no == seq_no))
    if not obj:
        raise HTTPException(status_code=404, detail="志愿者不存在")
    db.delete(obj)
    db.commit()
    return {"ok": True, "deleted": 1, "seq_no": seq_no, "entity": "volunteers"}


# =========================
# 匹配：运行 + 当前结果查询 + 导出
# =========================

_orchestrator = MatchingOrchestrator()
_store = MatchingStore()


@app.post("/api/matching/run-full", response_model=RunFullMatchResponse)
def run_full_match(db: Session = Depends(get_db)):
    """
    自动完成：清空旧结果 -> direct -> pre -> 落库当前结果
    """
    try:
        summary = _orchestrator.run_full_match(db)
        return summary
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"运行完整匹配失败: {e}") from e


@app.get("/api/matching/results", response_model=dict)
def get_final_results(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
):
    total, items = _store.list_final_results(db, offset=offset, limit=limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [FinalMatchResultOut.model_validate(x).model_dump() for x in items],
    }


@app.get("/api/matching/pairs", response_model=dict)
def get_pair_details(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=2000),
    phase: Optional[str] = Query(default=None, description="direct/pre"),
    selected_in_final: Optional[bool] = Query(default=None),
    student_seq: Optional[str] = Query(default=None),
    teacher_seq: Optional[str] = Query(default=None),
    include_raw: int = Query(default=0, ge=0, le=1, description="是否返回DS原文与错误信息"),
):
    total, items = _store.list_pair_details(
        db,
        offset=offset,
        limit=limit,
        phase=phase,
        selected_in_final=selected_in_final,
        student_seq=student_seq,
        teacher_seq=teacher_seq,
    )

    out_items = []
    for x in items:
        d = PairScoreDetailOut.model_validate(x).model_dump()
        if include_raw != 1:
            d["ds_subjective_reason_raw"] = None
            d["ds_special_reason_raw"] = None
            d["ds_subjective_error_message"] = None
            d["ds_special_error_message"] = None
        else:
            d["ds_subjective_reason_raw"] = x.ds_subjective_reason_raw
            d["ds_special_reason_raw"] = x.ds_special_reason_raw
            d["ds_subjective_error_message"] = x.ds_subjective_error_message
            d["ds_special_error_message"] = x.ds_special_error_message
        out_items.append(d)

    return {"total": total, "offset": offset, "limit": limit, "items": out_items}


@app.get("/api/matching/unmatched-students", response_model=dict)
def get_unmatched_students(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
):
    total, items = _store.list_unmatched_students(db, offset=offset, limit=limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [UnmatchedStudentOut.model_validate(x).model_dump() for x in items],
    }


@app.get("/api/matching/unused-volunteers", response_model=dict)
def get_unused_volunteers(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
):
    total, items = _store.list_unused_volunteers(db, offset=offset, limit=limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [UnusedVolunteerOut.model_validate(x).model_dump() for x in items],
    }


@app.get("/api/matching/export")
def export_matching_results(db: Session = Depends(get_db)):
    """
    导出4-sheet xlsx：
    - 最终匹配结果
    - 未匹配学生
    - 未使用老师
    - 全部合法Pair打分明细
    """
    try:
        content = build_matching_export_workbook_bytes(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {e}") from e

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"matching_export_{ts}.xlsx"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )