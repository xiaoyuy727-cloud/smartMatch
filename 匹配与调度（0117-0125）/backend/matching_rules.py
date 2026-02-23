# backend/matching_rules.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any

# 权重（可调参）
W_GRADE = 20.0
W_SUBJECT = 40.0
W_STYLE = 40.0   # Stage2: 由 DS 返回的 teaching_style_score + major_match_score 组成
W_SPECIAL = 20.0 # Stage2: 惩罚项范围 0 ~ -20


GRADE_MULT = {
    1: 1.0,         # 命中 grade1 -> 100%
    2: 2.0 / 3.0,   # grade2 -> 66.7%
    3: 1.0 / 3.0,   # grade3 -> 33.3%
}

PREF_WEIGHT = {1: 3, 2: 2, 3: 1}  # rank -> weight


def _to_int_safe(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _mode_compatible(student_mode: str, vol_mode: str) -> bool:
    if student_mode == "both" or vol_mode == "both":
        return True
    return student_mode == vol_mode


def _gender_compatible(student_gender: str, gender_requirement: str) -> bool:
    if gender_requirement == "none":
        return True
    return student_gender == gender_requirement


def is_legal_pair(student: Dict, volunteer: Dict) -> Tuple[bool, Optional[str]]:
    if not _mode_compatible(str(student.get("mode", "")), str(volunteer.get("mode", ""))):
        return False, "mode 不兼容"
    if not _gender_compatible(str(student.get("gender", "")), str(volunteer.get("gender_requirement", "none"))):
        return False, "性别要求不满足"
    return True, None


def grade_score(student: Dict, volunteer: Dict) -> float:
    gs = _to_int_safe(student.get("grade_stage"), 0)
    ranks = [
        _to_int_safe(volunteer.get("grade1"), 0),
        _to_int_safe(volunteer.get("grade2"), 0),
        _to_int_safe(volunteer.get("grade3"), 0),
    ]
    if gs in ranks:
        pos = ranks.index(gs) + 1  # 1/2/3
        return W_GRADE * GRADE_MULT[pos]
    return 0.0


def _pref_map_3(a: Any, b: Any, c: Any) -> Dict[int, Tuple[int, int]]:
    """
    返回 {subject_id: (rank, weight)}，自动把字符串科目转 int
    """
    m: Dict[int, Tuple[int, int]] = {}
    aa, bb, cc = _to_int_safe(a), _to_int_safe(b), _to_int_safe(c)
    if aa > 0:
        m[aa] = (1, PREF_WEIGHT[1])
    if bb > 0:
        m[bb] = (2, PREF_WEIGHT[2])
    if cc > 0:
        m[cc] = (3, PREF_WEIGHT[3])
    return m


def subject_score_and_best(student: Dict, volunteer: Dict):
    s_map = _pref_map_3(student.get("subj1"), student.get("subj2"), student.get("subj3"))
    v_map = _pref_map_3(volunteer.get("subj1"), volunteer.get("subj2"), volunteer.get("subj3"))

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

    subj_score = (best_raw / 9.0) * W_SUBJECT if best_raw > 0 else 0.0
    return subj_score, best_raw, best_subject_ids, best_details


def score_pair_v1(student: Dict, volunteer: Dict) -> Dict:
    """
    Stage1客观分 + 占位主观分（0分）
    """
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
            "total_score": -1e9,
            "best_subject_raw": 0,
            "best_subject_ids": [],
            "best_subject_details": [],

            # Stage2兼容字段（默认空）
            "teaching_style_score": 0.0,
            "major_match_score": 0.0,
            "llm_status": "not_run",
            "llm_model": None,
            "prompt_version_style": None,
            "prompt_version_major": None,
            "prompt_version_special": None,
            "llm_reason_style": None,
            "llm_reason_major": None,
            "llm_reason_special": None,
            "llm_confidence_style": None,
            "llm_confidence_major": None,
            "llm_confidence_special": None,
        }

    g = grade_score(student, volunteer)
    subj, best_raw, best_ids, best_details = subject_score_and_best(student, volunteer)
    st = 0.0
    base = g + subj + st
    pen = 0.0
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

        # Stage2兼容字段（默认空）
        "teaching_style_score": 0.0,
        "major_match_score": 0.0,
        "llm_status": "not_run",
        "llm_model": None,
        "prompt_version_style": None,
        "prompt_version_major": None,
        "prompt_version_special": None,
        "llm_reason_style": None,
        "llm_reason_major": None,
        "llm_reason_special": None,
        "llm_confidence_style": None,
        "llm_confidence_major": None,
        "llm_confidence_special": None,
    }


def apply_subjective_scores(base_score_obj: Dict, subjective: Dict | None) -> Dict:
    """
    将 DS 主观评分结果并入 score 对象，返回新 dict
    """
    sc = dict(base_score_obj)
    if not sc.get("is_legal", False):
        return sc
    if not subjective:
        return sc

    teaching_style_score = float(subjective.get("teaching_style_score", 0.0) or 0.0)
    major_match_score = float(subjective.get("major_match_score", 0.0) or 0.0)
    style_score = float(subjective.get("style_score", teaching_style_score + major_match_score) or 0.0)

    # 防御：style 总分裁剪到 0~40
    if style_score < 0:
        style_score = 0.0
    if style_score > W_STYLE:
        style_score = W_STYLE

    special_penalty = float(subjective.get("special_penalty", 0.0) or 0.0)
    if special_penalty > 0:
        special_penalty = 0.0
    if special_penalty < -W_SPECIAL:
        special_penalty = -W_SPECIAL

    sc["teaching_style_score"] = teaching_style_score
    sc["major_match_score"] = major_match_score
    sc["style_score"] = style_score
    sc["special_penalty"] = special_penalty

    # 重算 base / total
    sc["base_score"] = float(sc.get("grade_score", 0.0)) + float(sc.get("subject_score", 0.0)) + style_score
    sc["total_score"] = sc["base_score"] + special_penalty

    # 补充 Stage2 元信息
    for k in [
        "llm_status", "llm_model",
        "prompt_version_style", "prompt_version_major", "prompt_version_special",
        "llm_reason_style", "llm_reason_major", "llm_reason_special",
        "llm_confidence_style", "llm_confidence_major", "llm_confidence_special",
        "llm_rule_checks_style", "llm_rule_checks_major", "llm_rule_checks_special",
        "llm_elapsed_style_ms", "llm_elapsed_major_ms", "llm_elapsed_special_ms",
        "llm_raw_style", "llm_raw_major", "llm_raw_special",
    ]:
        if k in subjective:
            sc[k] = subjective[k]

    return sc