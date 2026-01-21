from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# 权重（可调参）
W_GRADE = 20.0
W_SUBJECT = 40.0
W_STYLE = 40.0  # V1 占位（DeepSeek）
W_SPECIAL = 20.0  # 这是“扣分项”上限（0~-20），V1 占位


GRADE_MULT = {
    1: 1.0,       # 命中 grade1 -> 100%
    2: 2.0 / 3.0, # grade2 -> 66.7%
    3: 1.0 / 3.0, # grade3 -> 33.3%
}

PREF_WEIGHT = {1: 3, 2: 2, 3: 1}  # rank -> weight


def _mode_compatible(student_mode: str, vol_mode: str) -> bool:
    # both 与任何兼容
    if student_mode == "both" or vol_mode == "both":
        return True
    return student_mode == vol_mode


def _gender_compatible(student_gender: str, gender_requirement: str) -> bool:
    # requirement: none/M/F
    if gender_requirement == "none":
        return True
    return student_gender == gender_requirement


def is_legal_pair(student: Dict, volunteer: Dict) -> Tuple[bool, Optional[str]]:
    if not _mode_compatible(student["mode"], volunteer["mode"]):
        return False, "mode 不兼容"
    if not _gender_compatible(student["gender"], volunteer["gender_requirement"]):
        return False, "性别要求不满足"
    return True, None


def grade_score(student: Dict, volunteer: Dict) -> float:
    gs = student["grade_stage"]
    ranks = [volunteer["grade1"], volunteer["grade2"], volunteer["grade3"]]
    if gs in ranks:
        pos = ranks.index(gs) + 1  # 1/2/3
        return W_GRADE * GRADE_MULT[pos]
    return 0.0


def _pref_map_3(a: int, b: int, c: int) -> Dict[int, Tuple[int, int]]:
    """
    返回 {subject_id: (rank, weight)}
    """
    m: Dict[int, Tuple[int, int]] = {}
    m[a] = (1, PREF_WEIGHT[1])
    m[b] = (2, PREF_WEIGHT[2])
    m[c] = (3, PREF_WEIGHT[3])
    return m


def subject_score_and_best(student: Dict, volunteer: Dict):
    s_map = _pref_map_3(student["subj1"], student["subj2"], student["subj3"])
    v_map = _pref_map_3(volunteer["subj1"], volunteer["subj2"], volunteer["subj3"])

    # 1..9 全部扫一遍（或只扫交集也行，这里扫全更直观）
    best_raw = 0
    per_subj = {}  # subject_id -> detail
    for sid in range(1, 10):
        s_rank, s_w = s_map.get(sid, (0, 0))
        v_rank, v_w = v_map.get(sid, (0, 0))
        prod = s_w * v_w
        per_subj[sid] = (s_rank, s_w, v_rank, v_w, prod)
        if prod > best_raw:
            best_raw = prod

    best_subject_ids: List[int] = []
    best_details: List[Dict] = []
    if best_raw > 0:
        for sid in range(1, 10):
            s_rank, s_w, v_rank, v_w, prod = per_subj[sid]
            if prod == best_raw:
                best_subject_ids.append(sid)
                best_details.append(
                    {
                        "subject_id": sid,
                        "student_rank": s_rank,
                        "student_weight": s_w,
                        "teacher_rank": v_rank,
                        "teacher_weight": v_w,
                        "product": prod,
                    }
                )

    # 映射到 40 分制：raw/9 * 40
    subj_score = (best_raw / 9.0) * W_SUBJECT if best_raw > 0 else 0.0
    return subj_score, best_raw, best_subject_ids, best_details


def style_score(student: Dict, volunteer: Dict) -> float:
    # V1：DeepSeek 占位，先 0
    return 0.0


def special_penalty(student: Dict, volunteer: Dict) -> float:
    # V1：DeepSeek 占位，先 0（不扣）
    # 后续可改成：根据 special_needs_text 与志愿者能力不匹配 -> -20 或 0~-20
    return 0.0


def score_pair_v1(student: Dict, volunteer: Dict) -> Dict:
    legal, reason = is_legal_pair(student, volunteer)
    if not legal:
        return {
            "is_legal": False,
            "illegal_reason": reason,
            "grade_score": 0.0,
            "subject_score": 0.0,
            "style_score": 0.0,
            "base_score": 0.0,
            "special_penalty": 0.0,
            "total_score": -1e9,  # 不参与排序
            "best_subject_raw": 0,
            "best_subject_ids": [],
            "best_subject_details": [],
        }

    g = grade_score(student, volunteer)
    subj, best_raw, best_ids, best_details = subject_score_and_best(student, volunteer)
    st = style_score(student, volunteer)
    base = g + subj + st
    pen = special_penalty(student, volunteer)
    total = base + pen

    return {
        "is_legal": True,
        "illegal_reason": None,
        "grade_score": g,
        "subject_score": subj,
        "style_score": st,
        "base_score": base,
        "special_penalty": pen,
        "total_score": total,
        "best_subject_raw": best_raw,
        "best_subject_ids": best_ids,
        "best_subject_details": best_details,
    }
