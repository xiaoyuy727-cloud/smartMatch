from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# -----------------------
# 硬约束：线上/线下合法性
# 规则：仅两种不合法：
#   student=offline & teacher=online
#   student=online  & teacher=offline
# 其他都合法（含任何一方 both）
# -----------------------

def is_tutoring_mode_compatible(student_mode: str, teacher_mode: str) -> bool:
    sm = (student_mode or "").strip().lower()
    tm = (teacher_mode or "").strip().lower()
    if sm == "offline" and tm == "online":
        return False
    if sm == "online" and tm == "offline":
        return False
    return True


# -----------------------
# 硬约束：性别要求
# 学生端对老师无要求
# 老师端对学生要求：F/M/N
# -----------------------

def is_gender_compatible(student_gender: str, teacher_requirement: str) -> bool:
    sg = (student_gender or "").strip().upper()
    req = (teacher_requirement or "N").strip().upper()
    if req == "N":
        return True
    return sg == req


def is_legal_pair(
    student_gender: str,
    student_mode: str,
    teacher_mode: str,
    teacher_student_gender_requirement: str,
) -> bool:
    return (
        is_tutoring_mode_compatible(student_mode, teacher_mode)
        and is_gender_compatible(student_gender, teacher_student_gender_requirement)
    )


# -----------------------
# 客观分：grade 20分
# 学生学段编码：1/2/3
# 老师偏好学段1/2/3：不空且不重复（由输入保证）
# 命中pref1: 20
# 命中pref2: 13.33
# 命中pref3: 6.67
# 未命中: 0
# -----------------------

def calc_grade_score(student_stage: int, pref1: int, pref2: int, pref3: int) -> float:
    if student_stage == pref1:
        return 20.00
    if student_stage == pref2:
        return 13.33
    if student_stage == pref3:
        return 6.67
    return 0.00


# -----------------------
# 客观分：subject 40分
# 学生/老师偏好1/2/3 赋分 3/2/1
# 计算3x3共9个组合乘积，取最大 best_raw in [0,9]
# 映射：subject = round(40 * best_raw / 9, 2)
# 0 表示无偏好，占位，不参与有效命中
# -----------------------

def _rank_score(rank_index: int) -> int:
    # rank_index: 0/1/2 -> 3/2/1
    return 3 - rank_index


def calc_best_subject_raw(
    s1: int, s2: int, s3: int,
    t1: int, t2: int, t3: int
) -> int:
    student = [s1, s2, s3]
    teacher = [t1, t2, t3]
    best = 0
    for si, scode in enumerate(student):
        if scode == 0:
            continue
        for ti, tcode in enumerate(teacher):
            if tcode == 0:
                continue
            if scode == tcode:
                raw = _rank_score(si) * _rank_score(ti)  # 1..9
                if raw > best:
                    best = raw
    return best


def calc_subject_score_from_best_raw(best_raw: int) -> float:
    if best_raw <= 0:
        return 0.00
    return round(40.0 * float(best_raw) / 9.0, 2)


# -----------------------
# 总分公式（允许为负）
# total = grade + subject + ds_subjective - ds_special_penalty
# -----------------------

def calc_total_score(
    grade_score: float,
    subject_score: float,
    ds_subjective_score: float,
    ds_special_penalty: float,
) -> float:
    return round(float(grade_score) + float(subject_score) + float(ds_subjective_score) - float(ds_special_penalty), 2)


def normalize_special_need_text(text: Optional[str]) -> str:
    if text is None:
        return ""
    return str(text).strip()


def has_effective_special_need(text: Optional[str]) -> bool:
    s = normalize_special_need_text(text)
    if not s:
        return False
    # 约定“无”表示无特殊需求
    if s == "无":
        return False
    # 容错
    if s.strip().lower() in {"none", "null", "n/a"}:
        return False
    return True


# -----------------------
# 排序 tie-break
# 同分：teacher_seq 小优先；再用 student_seq 做稳定键
# -----------------------

def _seq_key(seq: str) -> tuple[int, object]:
    s = (seq or "").strip()
    try:
        return (0, int(s))
    except Exception:
        return (1, s)


def pair_sort_key(total_score: float, teacher_seq: str, student_seq: str) -> tuple[float, tuple[int, object], tuple[int, object]]:
    # Python sort默认升序：用 -total 使 total 降序
    return (-float(total_score), _seq_key(teacher_seq), _seq_key(student_seq))