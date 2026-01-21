from __future__ import annotations
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from models import Student, Volunteer
from matching_rules import score_pair_v1


def _student_to_dict(s: Student) -> Dict:
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
    }


def _vol_to_dict(v: Volunteer) -> Dict:
    return {
        "seq_no": v.seq_no,
        "name": v.name,
        "gender": v.gender,
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
    }


def generate_candidates(
    db: Session,
    student_ids: Optional[List[int]] = None,
    volunteer_ids: Optional[List[int]] = None,
    match_mode: Optional[str] = None,  # direct/pre/None
) -> List[Dict]:
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

    candidates: List[Dict] = []
    for s in students:
        for v in vols:
            sc = score_pair_v1(s, v)
            if not sc["is_legal"]:
                continue
            candidates.append(
                {
                    "student": s,
                    "volunteer": v,
                    "score": sc,
                }
            )

    # 排序：total desc + priority desc + tie-break
    candidates.sort(
        key=lambda x: (
            x["score"]["total_score"],
            1 if x["student"]["is_priority"] else 0,
            x["score"]["best_subject_raw"],
            -x["student"]["seq_no"],  # 这里给个稳定性（也可改 asc）
            -x["volunteer"]["seq_no"],
        ),
        reverse=True,
    )
    return candidates


def preview_topk(
    db: Session,
    topk: int = 200,
    match_mode: Optional[str] = None,
) -> Dict:
    cand = generate_candidates(db=db, match_mode=match_mode)
    top = cand[:topk]
    return {"total_candidates": len(cand), "topk": top}


def _greedy_match(candidates: List[Dict], only_priority_students: bool) -> Tuple[List[Dict], set, Dict[int, int]]:
    """
    返回：
      matches(list of cand item),
      used_student_ids(set),
      remaining_vol_capacity(dict vol_id -> remaining cap)
    """
    remaining_cap: Dict[int, int] = {}
    for c in candidates:
        vid = c["volunteer"]["seq_no"]
        if vid not in remaining_cap:
            remaining_cap[vid] = int(c["volunteer"]["capacity"])

    used_students: set = set()
    matches: List[Dict] = []

    for c in candidates:
        sid = c["student"]["seq_no"]
        vid = c["volunteer"]["seq_no"]
        if sid in used_students:
            continue
        if remaining_cap.get(vid, 0) <= 0:
            continue
        if only_priority_students and not c["student"]["is_priority"]:
            continue

        # select
        matches.append(c)
        used_students.add(sid)
        remaining_cap[vid] -= 1

    return matches, used_students, remaining_cap


def run_match_v1(
    db: Session,
    match_mode: Optional[str] = None,  # direct/pre/None
) -> Dict:
    candidates = generate_candidates(db=db, match_mode=match_mode)

    # 第一遍：只匹配优先学生
    matches1, used_students1, remaining_cap = _greedy_match(candidates, only_priority_students=True)

    # 第二遍：匹配剩余（包含非优先）
    # 需要在第二遍里考虑第一遍已经用掉的学生与容量
    used_students = set(used_students1)
    matches = list(matches1)

    for c in candidates:
        sid = c["student"]["seq_no"]
        vid = c["volunteer"]["seq_no"]
        if sid in used_students:
            continue
        if remaining_cap.get(vid, 0) <= 0:
            continue

        matches.append(c)
        used_students.add(sid)
        remaining_cap[vid] -= 1

    # 计算未匹配
    all_students = [x.seq_no for x in db.query(Student.seq_no).all()]
    all_students = [x[0] if isinstance(x, tuple) else x for x in all_students]
    unmatched_students = [sid for sid in all_students if sid not in used_students]

    all_vols = db.query(Volunteer).all()
    unmatched_vols = []
    # 未匹配志愿者：容量完全没用到也算未匹配（简单定义）
    for v in all_vols:
        rem = remaining_cap.get(v.seq_no, v.capacity)
        if rem == v.capacity:
            unmatched_vols.append(v.seq_no)

    return {
        "matches": matches,
        "unmatched_students": unmatched_students,
        "unmatched_volunteers": unmatched_vols,
    }
