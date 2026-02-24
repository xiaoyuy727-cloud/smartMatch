from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RunFullMatchResponse(BaseModel):
    ok: bool = True
    cleared_old_results: bool = True

    total_students: int = 0
    total_volunteers: int = 0

    direct_volunteers: int = 0
    pre_volunteers: int = 0

    direct_matched: int = 0
    pre_matched: int = 0
    total_matched: int = 0

    unmatched_students: int = 0
    unused_volunteers: int = 0

    message: str = ""


class PairScoreDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phase: str

    student_seq: str
    student_name: str
    teacher_seq: str
    teacher_name: str

    student_tutoring_mode: str
    teacher_tutoring_mode: str
    student_is_priority: bool
    teacher_match_mode: str

    grade_score: float
    subject_score: float
    best_subject_raw: float

    ds_subjective_score: float
    ds_subjective_reason_summary: str
    ds_subjective_status: str
    ds_subjective_cache_hit: bool

    ds_special_penalty: float
    ds_special_reason_summary: str
    ds_special_status: str
    ds_special_cache_hit: bool

    total_score: float
    selected_in_final: bool

    # 可选展示（默认不返回，除非 include_raw=1）
    ds_subjective_reason_raw: Optional[str] = None
    ds_special_reason_raw: Optional[str] = None
    ds_subjective_error_message: Optional[str] = None
    ds_special_error_message: Optional[str] = None


class FinalMatchResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phase: str

    student_seq: str
    student_name: str
    teacher_seq: str
    teacher_name: str

    tutoring_mode: str
    teacher_match_mode: str

    grade_score: float
    subject_score: float
    ds_subjective_score: float
    ds_special_penalty: float
    total_score: float

    ds_subjective_reason_summary: str
    ds_special_reason_summary: str


class UnmatchedStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_seq: str
    student_name: str
    gender: str
    stage_code: int
    tutoring_mode: str
    is_priority: bool
    reason_summary: str


class UnusedVolunteerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_seq: str
    teacher_name: str
    gender: str
    tutoring_mode: str
    match_mode: str
    reason_summary: str


class PagedResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[Any] = Field(default_factory=list)