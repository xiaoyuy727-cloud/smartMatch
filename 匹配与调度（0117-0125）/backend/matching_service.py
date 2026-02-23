from __future__ import annotations
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session

from models import Student, Volunteer
from matching_rules import score_pair_v1


def _student_to_dict(s: Student) -> Dict:
    return {
        "seq_no": str(s.seq_no),
        "name": s.name,
        "gender": s.gender,
        "grade_stage": int(s.grade_stage),
        "mode": s.mode,
        "subj1": s.subj1,
        "subj2": s.subj2,
        "subj3": s.subj3,
        "is_priority": bool(s.is_priority),
        "weakness_text": s.weakness_text,
        "learning_style": s.learning_style,
        "interests_text": s.interests_text,
        "personality_text": s.personality_text,
        "special_needs_text": s.special_needs_text,
    }


def _vol_to_dict(v: Volunteer) -> Dict:
    return {
        "seq_no": str(v.seq_no),
        "name": v.name,
        "gender": v.gender,
        "mode": v.mode,
        "match_mode": v.match_mode,
        "gender_requirement": v.gender_requirement,
        "grade1": int(v.grade1),
        "grade2": int(v.grade2),
        "grade3": int(v.grade3),
        "subj1": v.subj1,
        "subj2": v.subj2,
        "subj3": v.subj3,
        "capacity": int(v.capacity),
        "teaching_style_text": v.teaching_style_text,
    }


def _normalize_id_list(ids: Optional[List[str]]) -> Optional[List[str]]:
    if ids is None:
        return None
    return [str(x) for x in ids]


def generate_candidates(
    db: Session,
    student_ids: Optional[List[str]] = None,
    volunteer_ids: Optional[List[str]] = None,
    match_mode: Optional[str] = None,  # direct/pre/None
    student_grade_stage: Optional[int] = None,
) -> List[Dict]:
    student_ids = _normalize_id_list(student_ids)
    volunteer_ids = _normalize_id_list(volunteer_ids)

    qs = db.query(Student)
    if student_ids is not None:
        if len(student_ids) == 0:
            return []
        qs = qs.filter(Student.seq_no.in_(student_ids))
    if student_grade_stage is not None:
        qs = qs.filter(Student.grade_stage == int(student_grade_stage))
    students = [_student_to_dict(x) for x in qs.all()]

    qv = db.query(Volunteer)
    if volunteer_ids is not None:
        if len(volunteer_ids) == 0:
            return []
        qv = qv.filter(Volunteer.seq_no.in_(volunteer_ids))
    if match_mode:
        qv = qv.filter(Volunteer.match_mode == match_mode)
    vols = [_vol_to_dict(x) for x in qv.all()]

    candidates: List[Dict] = []
    for s in students:
        for v in vols:
            sc = score_pair_v1(s, v)
            if not sc["is_legal"]:
                continue
            candidates.append({"student": s, "volunteer": v, "score": sc})

    # 排序：total desc + priority desc + best_subject_raw desc + seq_no asc
    candidates.sort(
        key=lambda x: (
            -float(x["score"]["total_score"]),
            -(1 if x["student"]["is_priority"] else 0),
            -int(x["score"].get("best_subject_raw", 0)),
            str(x["student"]["seq_no"]),
            str(x["volunteer"]["seq_no"]),
        )
    )
    return candidates


def preview_topk(
    db: Session,
    topk: int = 200,
    match_mode: Optional[str] = None,
    student_grade_stage: Optional[int] = None,
) -> Dict:
    cand = generate_candidates(db=db, match_mode=match_mode, student_grade_stage=student_grade_stage)
    top = cand[:topk]
    return {"total_candidates": len(cand), "topk": top}


def _init_remaining_cap(candidates: List[Dict]) -> Dict[str, int]:
    remaining_cap: Dict[str, int] = {}
    for c in candidates:
        vid = str(c["volunteer"]["seq_no"])
        if vid not in remaining_cap:
            remaining_cap[vid] = int(c["volunteer"]["capacity"])
    return remaining_cap


def _greedy_pass(
    candidates: List[Dict],
    used_students: Set[str],
    remaining_cap: Dict[str, int],
    only_priority_students: bool,
    round_type: str,
) -> List[Dict]:
    selected: List[Dict] = []
    order = 0

    for c in candidates:
        sid = str(c["student"]["seq_no"])
        vid = str(c["volunteer"]["seq_no"])

        if sid in used_students:
            continue
        if remaining_cap.get(vid, 0) <= 0:
            continue
        if only_priority_students and not bool(c["student"]["is_priority"]):
            continue

        used_students.add(sid)
        remaining_cap[vid] -= 1
        order += 1

        item = {
            "student": dict(c["student"]),
            "volunteer": dict(c["volunteer"]),
            "score": dict(c["score"]),
            "round_type": round_type,  # priority / normal
            "match_order": order,      # 本轮次内顺序
        }
        selected.append(item)

    return selected


def run_match_v1(
    db: Session,
    match_mode: Optional[str] = None,  # direct/pre/None
    student_ids: Optional[List[str]] = None,
    student_grade_stage: Optional[int] = None,
    volunteer_ids: Optional[List[str]] = None,
) -> Dict:
    student_ids = _normalize_id_list(student_ids)
    volunteer_ids = _normalize_id_list(volunteer_ids)

    candidates = generate_candidates(
        db=db,
        match_mode=match_mode,
        student_ids=student_ids,
        student_grade_stage=student_grade_stage,
        volunteer_ids=volunteer_ids,
    )

    remaining_cap = _init_remaining_cap(candidates)
    used_students: Set[str] = set()

    # 第一遍：只匹配优先学生
    matches1 = _greedy_pass(
        candidates=candidates,
        used_students=used_students,
        remaining_cap=remaining_cap,
        only_priority_students=True,
        round_type="priority",
    )

    # 第二遍：匹配剩余（包含非优先）
    matches2 = _greedy_pass(
        candidates=candidates,
        used_students=used_students,
        remaining_cap=remaining_cap,
        only_priority_students=False,
        round_type="normal",
    )

    matches = matches1 + matches2

    # 跨两轮的顺序（便于调试）
    for idx, m in enumerate(matches, start=1):
        m["global_match_order"] = idx

    # 学生范围（必须和本次 run 的输入范围一致）
    qs = db.query(Student.seq_no)
    if student_ids is not None:
        if len(student_ids) == 0:
            scoped_students: List[str] = []
        else:
            qs = qs.filter(Student.seq_no.in_(student_ids))
            if student_grade_stage is not None:
                qs = qs.filter(Student.grade_stage == int(student_grade_stage))
            scoped_students = [str(x[0]) for x in qs.all()]
    else:
        if student_grade_stage is not None:
            qs = qs.filter(Student.grade_stage == int(student_grade_stage))
        scoped_students = [str(x[0]) for x in qs.all()]

    unmatched_students = [sid for sid in scoped_students if sid not in used_students]

    # 志愿者范围
    qv = db.query(Volunteer)
    if volunteer_ids is not None:
        if len(volunteer_ids) == 0:
            scoped_vols: List[Volunteer] = []
        else:
            qv = qv.filter(Volunteer.seq_no.in_(volunteer_ids))
            if match_mode:
                qv = qv.filter(Volunteer.match_mode == match_mode)
            scoped_vols = qv.all()
    else:
        if match_mode:
            qv = qv.filter(Volunteer.match_mode == match_mode)
        scoped_vols = qv.all()

    unmatched_vols: List[str] = []
    for v in scoped_vols:
        vid = str(v.seq_no)
        # 没有任何合法候选对时，remaining_cap 中没有它 => 视为未匹配
        rem = remaining_cap.get(vid, int(v.capacity))
        if rem == int(v.capacity):
            unmatched_vols.append(vid)

    return {
        "matches": matches,
        "unmatched_students": unmatched_students,
        "unmatched_volunteers": unmatched_vols,
        "stats": {
            "total_candidates": len(candidates),
            "students_in_scope": len(scoped_students),
            "volunteers_in_scope": len(scoped_vols),
            "priority_matches": len(matches1),
            "normal_matches": len(matches2),
            "total_matches": len(matches),
        },
    }