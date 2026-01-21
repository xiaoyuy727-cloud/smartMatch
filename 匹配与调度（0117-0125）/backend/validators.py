import re
from typing import Any, Dict, List, Tuple

VALID_GENDERS = {"M", "F"}
VALID_GRADE_STAGE = {1, 2, 3}
VALID_MODE = {"online", "offline", "both"}
VALID_SUBJECTS = set(range(1, 10))
VALID_MATCH_MODE = {"direct", "pre"}
VALID_GENDER_REQ = {"none", "M", "F"}


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int,)):
        return int(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip() != "":
        try:
            f = float(v.strip())
            if f.is_integer():
                return int(f)
        except Exception:
            return None
    return None


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return int(v) != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "y"}:
            return True
        if s in {"0", "false", "no", "n", ""}:
            return False
    return False


def validate_student(row: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    返回：(clean_row, errors)
    """
    errors: List[str] = []
    clean = dict(row)

    seq_no = _as_int(clean.get("seq_no"))
    if seq_no is None:
        errors.append("seq_no 必须是整数")
    else:
        clean["seq_no"] = seq_no

    name = (clean.get("name") or "").strip()
    if not name:
        errors.append("name 必填")
    clean["name"] = name

    gender = (clean.get("gender") or "").strip().upper()
    if gender not in VALID_GENDERS:
        errors.append("gender 必须是 M/F")
    clean["gender"] = gender

    grade_stage = _as_int(clean.get("grade_stage"))
    if grade_stage not in VALID_GRADE_STAGE:
        errors.append("grade_stage 必须是 1/2/3")
    clean["grade_stage"] = grade_stage

    mode = (clean.get("mode") or "").strip().lower()
    if mode not in VALID_MODE:
        errors.append("mode 必须是 online/offline/both")
    clean["mode"] = mode

    for k in ["subj1", "subj2", "subj3"]:
        sv = _as_int(clean.get(k))
        if sv not in VALID_SUBJECTS:
            errors.append(f"{k} 必须是 1-9")
        clean[k] = sv

    # subj 不重复（建议）
    subs = [clean.get("subj1"), clean.get("subj2"), clean.get("subj3")]
    if len(set(subs)) != 3:
        errors.append("subj1/subj2/subj3 不能重复")

    # 可选字段统一为 str 或 None
    for k in [
        "weakness_text",
        "learning_style",
        "interests_text",
        "personality_text",
        "social_worker_name",
        "social_worker_phone",
        "special_needs_text",
    ]:
        v = clean.get(k)
        if v is None:
            clean[k] = None
        else:
            s = str(v).strip()
            clean[k] = s if s != "" else None

    clean["is_priority"] = _as_bool(clean.get("is_priority"))

    # phone 简单检查（可放宽）
    phone = clean.get("social_worker_phone")
    if phone:
        if not re.match(r"^[0-9+\-\s]{6,}$", phone):
            errors.append("social_worker_phone 格式不合法")

    return clean, errors


def validate_volunteer(row: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    clean = dict(row)

    seq_no = _as_int(clean.get("seq_no"))
    if seq_no is None:
        errors.append("seq_no 必须是整数")
    else:
        clean["seq_no"] = seq_no

    name = (clean.get("name") or "").strip()
    if not name:
        errors.append("name 必填")
    clean["name"] = name

    gender = (clean.get("gender") or "").strip().upper()
    if gender not in VALID_GENDERS:
        errors.append("gender 必须是 M/F")
    clean["gender"] = gender

    mode = (clean.get("mode") or "").strip().lower()
    if mode not in VALID_MODE:
        errors.append("mode 必须是 online/offline/both")
    clean["mode"] = mode

    match_mode = (clean.get("match_mode") or "").strip().lower()
    if match_mode not in VALID_MATCH_MODE:
        errors.append("match_mode 必须是 direct/pre")
    clean["match_mode"] = match_mode

    gender_req = (clean.get("gender_requirement") or "none").strip().upper()
    if gender_req == "NONE":
        gender_req = "none"
    if gender_req not in VALID_GENDER_REQ:
        errors.append("gender_requirement 必须是 none/M/F")
    clean["gender_requirement"] = gender_req

    for k in ["grade1", "grade2", "grade3"]:
        gv = _as_int(clean.get(k))
        if gv not in VALID_GRADE_STAGE:
            errors.append(f"{k} 必须是 1/2/3")
        clean[k] = gv
    # grade 不重复（建议）
    gs = [clean.get("grade1"), clean.get("grade2"), clean.get("grade3")]
    if len(set(gs)) != 3:
        errors.append("grade1/grade2/grade3 不能重复")

    for k in ["subj1", "subj2", "subj3"]:
        sv = _as_int(clean.get(k))
        if sv not in VALID_SUBJECTS:
            errors.append(f"{k} 必须是 1-9")
        clean[k] = sv
    subs = [clean.get("subj1"), clean.get("subj2"), clean.get("subj3")]
    if len(set(subs)) != 3:
        errors.append("subj1/subj2/subj3 不能重复")

    cap = _as_int(clean.get("capacity"))
    if cap is None:
        cap = 1
    if cap <= 0:
        errors.append("capacity 必须>=1")
    clean["capacity"] = cap

    # 可选字段
    for k in ["student_no", "email", "department_major", "teaching_style_text"]:
        v = clean.get(k)
        if v is None:
            clean[k] = None
        else:
            s = str(v).strip()
            clean[k] = s if s != "" else None

    clean["participated_before"] = _as_bool(clean.get("participated_before"))

    return clean, errors
