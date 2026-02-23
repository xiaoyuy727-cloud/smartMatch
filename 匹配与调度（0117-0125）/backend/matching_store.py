from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from models import MatchJob, MatchResult


def create_job(
    db: Session,
    *,
    algorithm_version: str,
    llm_enabled: bool,
    grade_stage_filter: Optional[int],
    params_json: Optional[Dict[str, Any]] = None,
) -> MatchJob:
    job = MatchJob(
        status="running",
        algorithm_version=algorithm_version,
        llm_enabled=bool(llm_enabled),
        grade_stage_filter=grade_stage_filter,
        params_json=params_json or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def save_match_results(db: Session, job_id: int, matches: List[Dict[str, Any]]) -> int:
    rows: List[MatchResult] = []
    for m in matches:
        s = m["student"]
        v = m["volunteer"]
        sc = m["score"]
        rows.append(
            MatchResult(
                job_id=job_id,
                stage=str(m.get("stage") or ""),
                round_type=str(m.get("round_type") or "normal"),
                match_order=int(m.get("match_order") or m.get("global_match_order") or 0),
                student_seq_no=str(s["seq_no"]),
                student_name_snapshot=str(s["name"]),
                volunteer_seq_no=str(v["seq_no"]),
                volunteer_name_snapshot=str(v["name"]),
                total_score=float(sc.get("total_score", 0.0)),
                base_score=float(sc.get("base_score", 0.0)),
                grade_score=float(sc.get("grade_score", 0.0)),
                subject_score=float(sc.get("subject_score", 0.0)),
                style_score=float(sc.get("style_score", 0.0)),
                special_penalty=float(sc.get("special_penalty", 0.0)),
                best_subject_raw=int(sc.get("best_subject_raw", 0) or 0),
                best_subject_ids_json=list(sc.get("best_subject_ids") or []),
                best_subject_details_json=list(sc.get("best_subject_details") or []),
            )
        )
    if rows:
        db.add_all(rows)
        db.commit()
    return len(rows)


def finish_job_success(db: Session, job_id: int, summary_json: Dict[str, Any]) -> MatchJob:
    job = db.get(MatchJob, job_id)
    if not job:
        raise ValueError(f"match job not found: {job_id}")
    job.status = "success"
    job.summary_json = summary_json
    from sqlalchemy import func
    job.finished_at = func.now()
    db.commit()
    db.refresh(job)
    return job


def finish_job_failed(db: Session, job_id: int, error_message: str) -> None:
    try:
        db.rollback()
    except Exception:
        pass

    job = db.get(MatchJob, job_id)
    if not job:
        return
    job.status = "failed"
    job.error_message = (error_message or "")[:5000]
    from sqlalchemy import func
    job.finished_at = func.now()
    db.commit()


def list_jobs(db: Session, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    items = (
        db.query(MatchJob)
        .order_by(MatchJob.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    out: List[Dict[str, Any]] = []
    for j in items:
        summary = j.summary_json or {}
        final_stats = (summary.get("final_stats") or {}) if isinstance(summary, dict) else {}
        out.append(
            {
                "id": j.id,
                "status": j.status,
                "algorithm_version": j.algorithm_version,
                "llm_enabled": bool(j.llm_enabled),
                "grade_stage_filter": j.grade_stage_filter,
                "created_at": j.created_at.isoformat() if getattr(j, "created_at", None) else None,
                "finished_at": j.finished_at.isoformat() if getattr(j, "finished_at", None) else None,
                "summary": summary,
                "total_matches": int(final_stats.get("total_matches", 0) or 0),
                "unmatched_students_count": int(final_stats.get("unmatched_students_count", 0) or 0),
                "unmatched_volunteers_count": int(final_stats.get("unmatched_volunteers_count", 0) or 0),
            }
        )
    return out


def get_job_detail(db: Session, job_id: int) -> Optional[Dict[str, Any]]:
    job = db.get(MatchJob, job_id)
    if not job:
        return None

    rows = (
        db.query(MatchResult)
        .filter(MatchResult.job_id == job_id)
        .order_by(MatchResult.stage.asc(), MatchResult.match_order.asc(), MatchResult.id.asc())
        .all()
    )

    results = []
    for r in rows:
        results.append(
            {
                "id": r.id,
                "job_id": r.job_id,
                "stage": r.stage,
                "round_type": r.round_type,
                "match_order": r.match_order,
                "student_seq_no": r.student_seq_no,
                "student_name": r.student_name_snapshot,
                "volunteer_seq_no": r.volunteer_seq_no,
                "volunteer_name": r.volunteer_name_snapshot,
                "total_score": r.total_score,
                "base_score": r.base_score,
                "grade_score": r.grade_score,
                "subject_score": r.subject_score,
                "style_score": r.style_score,
                "special_penalty": r.special_penalty,
                "best_subject_raw": r.best_subject_raw,
                "best_subject_ids": r.best_subject_ids_json or [],
                "best_subject_details": r.best_subject_details_json or [],
            }
        )

    return {
        "job": {
            "id": job.id,
            "status": job.status,
            "algorithm_version": job.algorithm_version,
            "llm_enabled": bool(job.llm_enabled),
            "grade_stage_filter": job.grade_stage_filter,
            "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
            "finished_at": job.finished_at.isoformat() if getattr(job, "finished_at", None) else None,
            "params": job.params_json or {},
            "summary": job.summary_json or {},
            "error_message": job.error_message,
        },
        "results": results,
    }


def count_jobs(db: Session) -> int:
    return int(db.query(MatchJob).count())