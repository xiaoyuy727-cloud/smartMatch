from __future__ import annotations

import math
from typing import Any, Callable, Optional


STUDENT_COLUMN_COUNT = 16
VOLUNTEER_COLUMN_COUNT = 18

VALID_GENDERS = {"M", "F"}
VALID_GENDER_REQUIREMENTS = {"M", "F", "N"}
VALID_STAGE_CODES = {1, 2, 3}
VALID_TUTORING_MODES = {"offline", "online", "both"}
VALID_MATCH_MODES = {"direct", "pre"}
VALID_SUBJECT_CODES = set(range(0, 10))  # 0~9


def _is_nan(value: Any) -> bool:
    try:
        return isinstance(value, float) and math.isnan(value)
    except Exception:
        return False


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if _is_nan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _to_clean_str(value: Any, default: Optional[str] = None) -> Optional[str]:
    if is_blank(value):
        return default
    s = str(value).strip()
    # 处理 Excel 中数值被读取成 x.0 的情况（尤其是序号）
    if s.endswith(".0"):
        try:
            f = float(s)
            if f.is_integer():
                return str(int(f))
        except Exception:
            pass
    return s


def _parse_int(value: Any, field_name: str, errors: list[str]) -> Optional[int]:
    if is_blank(value):
        errors.append(f"{field_name}为空")
        return None
    try:
        # pandas 可能给出 float
        if isinstance(value, float):
            if not value.is_integer():
                errors.append(f"{field_name}不是整数: {value}")
                return None
            return int(value)
        s = str(value).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return int(s)
    except Exception:
        errors.append(f"{field_name}无法解析为整数: {value}")
        return None


def _parse_bool01(value: Any, field_name: str, errors: list[str]) -> Optional[bool]:
    i = _parse_int(value, field_name, errors)
    if i is None:
        return None
    if i not in (0, 1):
        errors.append(f"{field_name}必须是0或1，实际为: {i}")
        return None
    return bool(i)


def _parse_gender_mf(value: Any, field_name: str, errors: list[str]) -> Optional[str]:
    s = _to_clean_str(value)
    if s is None:
        errors.append(f"{field_name}为空")
        return None
    s = s.upper()
    if s not in VALID_GENDERS:
        errors.append(f"{field_name}必须是M/F，实际为: {s}")
        return None
    return s


def _parse_gender_requirement(value: Any, field_name: str, errors: list[str]) -> Optional[str]:
    s = _to_clean_str(value)
    if s is None:
        errors.append(f"{field_name}为空")
        return None
    s = s.upper()
    if s not in VALID_GENDER_REQUIREMENTS:
        errors.append(f"{field_name}必须是F/M/N，实际为: {s}")
        return None
    return s


def _parse_stage_code(value: Any, field_name: str, errors: list[str]) -> Optional[int]:
    i = _parse_int(value, field_name, errors)
    if i is None:
        return None
    if i not in VALID_STAGE_CODES:
        errors.append(f"{field_name}必须是1/2/3，实际为: {i}")
        return None
    return i


def _parse_subject_code(value: Any, field_name: str, errors: list[str]) -> Optional[int]:
    i = _parse_int(value, field_name, errors)
    if i is None:
        return None
    if i not in VALID_SUBJECT_CODES:
        errors.append(f"{field_name}必须是0~9，实际为: {i}")
        return None
    return i


def _parse_tutoring_mode(value: Any, field_name: str, errors: list[str]) -> Optional[str]:
    s = _to_clean_str(value)
    if s is None:
        errors.append(f"{field_name}为空")
        return None
    s = s.strip().lower()
    if s not in VALID_TUTORING_MODES:
        errors.append(f"{field_name}必须是offline/online/both，实际为: {s}")
        return None
    return s


def _parse_match_mode(value: Any, field_name: str, errors: list[str]) -> Optional[str]:
    s = _to_clean_str(value)
    if s is None:
        errors.append(f"{field_name}为空")
        return None
    s = s.strip().lower()
    if s not in VALID_MATCH_MODES:
        errors.append(f"{field_name}必须是direct/pre，实际为: {s}")
        return None
    return s


def _parse_text(value: Any, field_name: str, errors: list[str], default: str = "无") -> str:
    s = _to_clean_str(value, default=default)
    if s is None:
        # 理论上不会到这里，因为 default 已给
        errors.append(f"{field_name}为空")
        return default
    return s


def _normalize_row_list(raw_row: list[Any]) -> list[Any]:
    # 保持原顺序，统一为 Python 基本类型（不强制全转字符串）
    return list(raw_row)


def validate_student_row(raw_row: list[Any], row_no: int) -> dict[str, Any]:
    """
    返回：
    {
      "row_no": int,
      "data": dict | None,
      "errors": [..]
    }
    """
    row = _normalize_row_list(raw_row)
    errors: list[str] = []

    if len(row) != STUDENT_COLUMN_COUNT:
        return {
            "row_no": row_no,
            "data": None,
            "errors": [f"列数错误：应为{STUDENT_COLUMN_COUNT}列，实际为{len(row)}列"],
        }

    seq_no = _to_clean_str(row[0])
    if not seq_no:
        errors.append("序号为空")

    name = _to_clean_str(row[1])
    if not name:
        errors.append("名字为空")

    gender = _parse_gender_mf(row[2], "性别", errors)
    stage_code = _parse_stage_code(row[3], "学段", errors)
    tutoring_mode = _parse_tutoring_mode(row[4], "线上/线下", errors)

    subj1 = _parse_subject_code(row[5], "偏好科目1", errors)
    subj2 = _parse_subject_code(row[6], "偏好科目2", errors)
    subj3 = _parse_subject_code(row[7], "偏好科目3", errors)

    student_profile = _parse_text(row[8], "学生情况描述", errors, default="无")
    learning_style = _parse_text(row[9], "学习风格描述", errors, default="无")
    interests = _parse_text(row[10], "学生兴趣爱好", errors, default="无")
    personality = _parse_text(row[11], "学生性格", errors, default="无")

    social_worker_name = _parse_text(row[12], "社工姓名", errors, default="无")
    social_worker_phone = _parse_text(row[13], "社工电话", errors, default="无")

    is_priority = _parse_bool01(row[14], "是否有优先", errors)
    special_need = _parse_text(row[15], "特殊需求", errors, default="无")

    if errors:
        return {"row_no": row_no, "data": None, "errors": errors}

    data = {
        "seq_no": seq_no,
        "name": name,
        "gender": gender,
        "stage_code": stage_code,
        "tutoring_mode": tutoring_mode,
        "subj1": subj1,
        "subj2": subj2,
        "subj3": subj3,
        "student_profile": student_profile,
        "learning_style": learning_style,
        "interests": interests,
        "personality": personality,
        "social_worker_name": social_worker_name,
        "social_worker_phone": social_worker_phone,
        "is_priority": is_priority,
        "special_need": special_need,
    }
    return {"row_no": row_no, "data": data, "errors": []}


def validate_volunteer_row(raw_row: list[Any], row_no: int) -> dict[str, Any]:
    row = _normalize_row_list(raw_row)
    errors: list[str] = []

    if len(row) != VOLUNTEER_COLUMN_COUNT:
        return {
            "row_no": row_no,
            "data": None,
            "errors": [f"列数错误：应为{VOLUNTEER_COLUMN_COUNT}列，实际为{len(row)}列"],
        }

    seq_no = _to_clean_str(row[0])
    if not seq_no:
        errors.append("序号为空")

    name = _to_clean_str(row[1])
    if not name:
        errors.append("姓名为空")

    gender = _parse_gender_mf(row[2], "性别", errors)
    student_no = _parse_text(row[3], "学号", errors, default="")
    email = _parse_text(row[4], "学邮", errors, default="")
    department = _parse_text(row[5], "院系", errors, default="无")

    tutoring_mode = _parse_tutoring_mode(row[6], "辅导方式", errors)
    match_mode = _parse_match_mode(row[7], "匹配模式", errors)

    joined_before = _parse_bool01(row[8], "是否参加过过去的活动", errors)
    personality = _parse_text(row[9], "个人性格", errors, default="无")
    student_gender_requirement = _parse_gender_requirement(row[10], "对学生性别要求", errors)

    subj1 = _parse_subject_code(row[11], "偏好科目1", errors)
    subj2 = _parse_subject_code(row[12], "偏好科目2", errors)
    subj3 = _parse_subject_code(row[13], "偏好科目3", errors)

    stage_pref1 = _parse_stage_code(row[14], "偏好学段1", errors)
    stage_pref2 = _parse_stage_code(row[15], "偏好学段2", errors)
    stage_pref3 = _parse_stage_code(row[16], "偏好学段3", errors)

    capacity = _parse_int(row[17], "可带学生数", errors)
    if capacity is not None and capacity <= 0:
        errors.append(f"可带学生数必须大于0，实际为: {capacity}")

    if errors:
        return {"row_no": row_no, "data": None, "errors": errors}

    data = {
        "seq_no": seq_no,
        "name": name,
        "gender": gender,
        "student_no": student_no,
        "email": email,
        "department": department,
        "tutoring_mode": tutoring_mode,
        "match_mode": match_mode,
        "joined_before": joined_before,
        "personality": personality,
        "student_gender_requirement": student_gender_requirement,
        "subj1": subj1,
        "subj2": subj2,
        "subj3": subj3,
        "stage_pref1": stage_pref1,
        "stage_pref2": stage_pref2,
        "stage_pref3": stage_pref3,
        "capacity": capacity,
    }
    return {"row_no": row_no, "data": data, "errors": []}