# backend/matching_service.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.orm import Session

from models import Student, Volunteer
from matching_rules import score_pair_v1, apply_subjective_scores
from ds_config import DSConfig
from ds_client import DeepSeekClient
from ds_scoring_service import score_subjective_pair


def _student_to_dict(s: Student) -> Dict[str, Any]:
    return {
        "seq_no": s.seq_no,
        "name": s.name,
        "gender": s.gender,
        "grade_stage": s.grade_stage,
        "mode": s.mode,
        "subj1": s.subj1,
        "subj2": s.subj2,
        "subj3": s.subj3,
        "is_priority": s.is_priority,
        "weakness_text": s.weakness_text,
        "learning_style": s.learning_style,
        "interests_text": s.interests_text,
        "personality_text": s.personality_text,
        "special_needs_text": s.special_needs_text,
        "social_worker_name": s.social_worker_name,
        "social_worker_phone": s.social_worker_phone,
    }


def _vol_to_dict(v: Volunteer) -> Dict[str, Any]:
    return {
        "seq_no": v.seq_no,
        "name": v.name,
        "gender": v.gender,
        "student_no": v.student_no,
        "email": v.email,
        "department_major": v.department_major,
        "mode": v.mode,
        "match_mode": v.match_mode,
        "gender_requirement": v.gender_requirement,
        "grade1": v.grade1,
        "grade2": v.grade2,
        "grade3": v.grade3,
        "subj1": v.subj1,
        "subj2": v.subj2,
        "subj3": v.subj3,
        "capacity": v.capacity,
        "teaching_style_text": v.teaching_style_text,
        "participated_before": v.participated_before,
    }


def _build_llm_client_if_enabled(llm_enabled: bool) -> tuple[DeepSeekClient | None, DSConfig, str | None]:
    cfg = DSConfig.from_env()
    # 接口参数优先级 > 环境变量（在调用层覆盖 cfg.enabled）
    cfg.enabled = bool(llm_enabled)
    ok, err = cfg.validate()
    if not ok:
        return None, cfg, err
    if not cfg.enabled:
        return None, cfg, None
    return DeepSeekClient(cfg), cfg, None


def generate_candidates(
    db: Session,
    student_ids: Optional[List[str]] = None,
    volunteer_ids: Optional[List[str]] = None,
    match_mode: Optional[str] = None,  # direct/pre/None
    llm_enabled: bool = False,
) -> Tuple[List[Dict], Dict]:
    qs = db.query(Student)
    if student_ids:
        qs = qs.filter(Student.seq_no.in_(student_ids))
    students = [_student_to_dict(x) for x in qs.all()]

    qv = db.query(Volunteer)
    if volunteer_ids:
        qv = qv.filter(Volunteer.seq_no.in_(volunteer_ids))
    if match_mode:
        qv = qv.filter(Volunteer.match_mode == match_mode)
    vols = [_vol_to_dict(x) for x in qv.all()]

    client, cfg, cfg_err = _build_llm_client_if_enabled(llm_enabled=llm_enabled)

    llm_stats = {
        "enabled": bool(llm_enabled),
        "configured": bool(client is not None),
        "config_error": cfg_err,
        "calls_pairs": 0,           # 候选对层面计数
        "calls_dimensions": 0,      # 维度调用总数（每对3次）
        "ok_pairs": 0,
        "partial_pairs": 0,
        "fallback_pairs": 0,
    }

    candidates: List[Dict] = []
    for s in students:
        for v in vols:
            sc = score_pair_v1(s, v)
            if not sc["is_legal"]:
                continue

            if client is not None:
                llm_stats["calls_pairs"] += 1
                llm_stats["calls_dimensions"] += 3
                subjective = score_subjective_pair(student=s, volunteer=v, client=client)
                sc = apply_subjective_scores(sc, subjective)

                st = sc.get("llm_status")
                if st == "ok":
                    llm_stats["ok_pairs"] += 1
                elif st == "partial":
                    llm_stats["partial_pairs"] += 1
                else:
                    llm_stats["fallback_pairs"] += 1
            else:
                # 未启用或配置失败时，保持 Stage1 基础分；若显式启用但配置错，标记下
                if llm_enabled and cfg_err:
                    sc["llm_status"] = "config_error"

            candidates.append({"student": s, "volunteer": v, "score": sc})

    # 排序：total desc + priority desc + best_subject_raw desc + tie-break
    candidates.sort(
        key=lambda x: (
            float(x["score"].get("total_score", -1e9)),
            1 if x["student"].get("is_priority") else 0,
            int(x["score"].get("best_subject_raw", 0)),
            str(x["student"].get("seq_no", "")),
            str(x["volunteer"].get("seq_no", "")),
        ),
        reverse=True,
    )

    stats = {
        "students_count": len(students),
        "volunteers_count": len(vols),
        "total_candidates": len(candidates),
        "llm_stats": llm_stats,
    }
    return candidates, stats


def preview_topk(
    db: Session,
    topk: int = 200,
    match_mode: Optional[str] = None,
    llm_enabled: bool = False,
) -> Dict:
    cand, stats = generate_candidates(db=db, match_mode=match_mode, llm_enabled=llm_enabled)
    top = cand[:topk]
    return {
        "total_candidates": len(cand),
        "topk": top,
        "stats": {
            **stats,
            "returned_topk": len(top),
        },
    }


def _greedy_match(candidates: List[Dict], only_priority_students: bool) -> Tuple[List[Dict], set[str], Dict[str, int]]:
    """
    返回：
      matches(list of cand item),
      used_student_ids(set),
      remaining_vol_capacity(dict vol_id -> remaining cap)
    """
    remaining_cap: Dict[str, int] = {}
    for c in candidates:
        vid = str(c["volunteer"]["seq_no"])
        if vid not in remaining_cap:
            remaining_cap[vid] = int(c["volunteer"].get("capacity", 1) or 1)

    used_students: set[str] = set()
    matches: List[Dict] = []

    for c in candidates:
        sid = str(c["student"]["seq_no"])
        vid = str(c["volunteer"]["seq_no"])
        if sid in used_students:
            continue
        if remaining_cap.get(vid, 0) <= 0:
            continue
        if only_priority_students and not bool(c["student"].get("is_priority")):
            continue

        matches.append(c)
        used_students.add(sid)
        remaining_cap[vid] -= 1

    return matches, used_students, remaining_cap


def run_match_v1(
    db: Session,
    match_mode: Optional[str] = None,  # direct/pre/None
    llm_enabled: bool = False,
) -> Dict:
    candidates, cand_stats = generate_candidates(db=db, match_mode=match_mode, llm_enabled=llm_enabled)

    # 第一遍：只匹配优先学生
    matches1, used_students1, remaining_cap = _greedy_match(candidates, only_priority_students=True)

    # 第二遍：匹配剩余（包含非优先）
    used_students = set(used_students1)
    matches = list(matches1)

    for c in candidates:
        sid = str(c["student"]["seq_no"])
        vid = str(c["volunteer"]["seq_no"])
        if sid in used_students:
            continue
        if remaining_cap.get(vid, 0) <= 0:
            continue

        matches.append(c)
        used_students.add(sid)
        remaining_cap[vid] -= 1

    # 未匹配学生（注意：如果 match_mode=direct/pre，这里通常仍是“全学生集合”，保留原逻辑）
    all_students = [x[0] for x in db.query(Student.seq_no).all()]
    unmatched_students = [sid for sid in all_students if str(sid) not in used_students]

    all_vols = db.query(Volunteer).all()
    unmatched_vols = []
    for v in all_vols:
        rem = remaining_cap.get(str(v.seq_no), int(v.capacity))
        if rem == int(v.capacity):
            unmatched_vols.append(v.seq_no)

    return {
        "matches": matches,
        "unmatched_students": unmatched_students,
        "unmatched_volunteers": unmatched_vols,
        "stats": {
            **cand_stats,
            "matches_count": len(matches),
            "priority_first_pass_matches": len(matches1),
            "second_pass_matches": len(matches) - len(matches1),
            "unmatched_students_count": len(unmatched_students),
            "unmatched_volunteers_count": len(unmatched_vols),
        },
    }