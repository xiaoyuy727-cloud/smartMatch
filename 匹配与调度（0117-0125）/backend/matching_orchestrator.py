from __future__ import annotations
from typing import Any, Dict, List, Optional
import traceback

from sqlalchemy.orm import Session

from models import Student, Volunteer
from matching_service import run_match_v1
from matching_store import (
    create_job,
    save_match_results,
    finish_job_success,
    finish_job_failed,
)


ALGO_VERSION = "v1_greedy_direct_then_pre"


def _get_student_scope_ids(db: Session, grade_stage_filter: Optional[int]) -> List[str]:
    q = db.query(Student.seq_no)
    if grade_stage_filter is not None:
        q = q.filter(Student.grade_stage == int(grade_stage_filter))
    return [str(x[0]) for x in q.all()]


def _count_volunteers_by_mode(db: Session, match_mode: str) -> int:
    return int(db.query(Volunteer).filter(Volunteer.match_mode == match_mode).count())


def _annotate_stage(matches: List[Dict[str, Any]], stage: str) -> List[Dict[str, Any]]:
    out = []
    for idx, m in enumerate(matches, start=1):
        item = dict(m)
        item["stage"] = stage
        item["match_order"] = idx  # 本阶段顺序
        out.append(item)
    return out


def _build_summary(
    *,
    grade_stage_filter: Optional[int],
    input_students_count: int,
    direct_vol_count: int,
    pre_vol_count: int,
    direct_run: Dict[str, Any],
    pre_run: Dict[str, Any],
    final_unmatched_students: List[str],
    final_unmatched_volunteers: List[str],
) -> Dict[str, Any]:
    direct_matches = direct_run.get("matches", [])
    pre_matches = pre_run.get("matches", [])
    direct_stats = direct_run.get("stats", {})
    pre_stats = pre_run.get("stats", {})

    summary = {
        "algorithm_version": ALGO_VERSION,
        "llm_enabled": False,
        "filters": {"grade_stage": grade_stage_filter},
        "input_counts": {
            "students": input_students_count,
            "volunteers_direct": direct_vol_count,
            "volunteers_pre": pre_vol_count,
        },
        "stage_stats": {
            "direct": {
                "candidates": int(direct_stats.get("total_candidates", 0) or 0),
                "matches": len(direct_matches),
                "priority_matches": int(direct_stats.get("priority_matches", 0) or 0),
                "normal_matches": int(direct_stats.get("normal_matches", 0) or 0),
                "unmatched_students_after_stage": len(direct_run.get("unmatched_students", [])),
                "unmatched_volunteers_in_stage": len(direct_run.get("unmatched_volunteers", [])),
            },
            "pre": {
                "candidates": int(pre_stats.get("total_candidates", 0) or 0),
                "matches": len(pre_matches),
                "priority_matches": int(pre_stats.get("priority_matches", 0) or 0),
                "normal_matches": int(pre_stats.get("normal_matches", 0) or 0),
                "unmatched_students_after_stage": len(pre_run.get("unmatched_students", [])),
                "unmatched_volunteers_in_stage": len(pre_run.get("unmatched_volunteers", [])),
            },
        },
        "final_stats": {
            "total_matches": len(direct_matches) + len(pre_matches),
            "unmatched_students_count": len(final_unmatched_students),
            "unmatched_volunteers_count": len(final_unmatched_volunteers),
        },
        "unmatched_students": final_unmatched_students,
        "unmatched_volunteers": final_unmatched_volunteers,
    }
    return summary


def run_full_match_v1(
    db: Session,
    *,
    grade_stage_filter: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Stage1 完整流程：
      1) direct 老师池匹配（优先 -> 普通）
      2) 用剩余学生去 pre 老师池匹配（优先 -> 普通）
      3) 结果入库（match_jobs + match_results）
      4) 返回 job_id + summary
    """
    params = {
        "grade_stage_filter": grade_stage_filter,
        "llm_enabled": False,
    }

    job = create_job(
        db=db,
        algorithm_version=ALGO_VERSION,
        llm_enabled=False,
        grade_stage_filter=grade_stage_filter,
        params_json=params,
    )
    job_id = job.id

    try:
        initial_student_ids = _get_student_scope_ids(db, grade_stage_filter=grade_stage_filter)
        direct_vol_count = _count_volunteers_by_mode(db, "direct")
        pre_vol_count = _count_volunteers_by_mode(db, "pre")

        # direct 阶段
        direct_run = run_match_v1(
            db=db,
            match_mode="direct",
            student_ids=initial_student_ids,
        )
        direct_matches = _annotate_stage(direct_run.get("matches", []), stage="direct")
        remain_after_direct = [str(x) for x in direct_run.get("unmatched_students", [])]

        # pre 阶段（仅剩余学生）
        if remain_after_direct:
            pre_run = run_match_v1(
                db=db,
                match_mode="pre",
                student_ids=remain_after_direct,
            )
        else:
            pre_run = {
                "matches": [],
                "unmatched_students": [],
                "unmatched_volunteers": [str(v.seq_no) for v in db.query(Volunteer).filter(Volunteer.match_mode == "pre").all()],
                "stats": {
                    "total_candidates": 0,
                    "students_in_scope": 0,
                    "volunteers_in_scope": pre_vol_count,
                    "priority_matches": 0,
                    "normal_matches": 0,
                    "total_matches": 0,
                },
            }
        pre_matches = _annotate_stage(pre_run.get("matches", []), stage="pre")

        all_matches = direct_matches + pre_matches
        final_unmatched_students = [str(x) for x in pre_run.get("unmatched_students", [])]
        final_unmatched_volunteers = sorted(
            set([str(x) for x in direct_run.get("unmatched_volunteers", [])] + [str(x) for x in pre_run.get("unmatched_volunteers", [])])
        )

        # 入库
        save_match_results(db=db, job_id=job_id, matches=all_matches)

        # 汇总
        summary = _build_summary(
            grade_stage_filter=grade_stage_filter,
            input_students_count=len(initial_student_ids),
            direct_vol_count=direct_vol_count,
            pre_vol_count=pre_vol_count,
            direct_run=direct_run,
            pre_run=pre_run,
            final_unmatched_students=final_unmatched_students,
            final_unmatched_volunteers=final_unmatched_volunteers,
        )
        finish_job_success(db=db, job_id=job_id, summary_json=summary)

        return {
            "job_id": job_id,
            "status": "success",
            "summary": summary,
            "matches_count": len(all_matches),
        }

    except Exception:
        err = traceback.format_exc()
        finish_job_failed(db=db, job_id=job_id, error_message=err)
        raise