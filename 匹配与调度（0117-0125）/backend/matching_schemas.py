from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class BestSubjectDetail(BaseModel):
    subject_id: int
    student_rank: int
    student_weight: int
    teacher_rank: int
    teacher_weight: int
    product: int  # 0..9


class CandidatePairOut(BaseModel):
    student_seq_no: str
    student_name: str
    student_is_priority: bool
    student_grade_stage: Optional[int] = None
    student_mode: Optional[str] = None

    volunteer_seq_no: str
    volunteer_name: str
    volunteer_match_mode: str
    volunteer_capacity: int
    volunteer_mode: Optional[str] = None

    is_legal: bool
    illegal_reason: Optional[str] = None

    grade_score: float
    subject_score: float
    style_score: float
    base_score: float

    special_penalty: float
    total_score: float

    best_subject_raw: int
    best_subject_ids: List[int] = Field(default_factory=list)
    best_subject_details: List[BestSubjectDetail] = Field(default_factory=list)


class MatchPreviewOut(BaseModel):
    total_candidates: int
    topk: List[CandidatePairOut]


class MatchPairOut(BaseModel):
    student_seq_no: str
    student_name: str
    volunteer_seq_no: str
    volunteer_name: str

    stage: Optional[str] = None          # direct/pre（Stage1历史结果会有）
    round_type: Optional[str] = None     # priority/normal
    match_order: Optional[int] = None    # 本阶段选中顺序

    total_score: float
    base_score: float
    grade_score: float
    subject_score: float
    style_score: float
    special_penalty: float

    best_subject_raw: int
    best_subject_ids: List[int] = Field(default_factory=list)
    best_subject_details: List[BestSubjectDetail] = Field(default_factory=list)


class MatchRunOut(BaseModel):
    matches: List[MatchPairOut]
    unmatched_students: List[str]
    unmatched_volunteers: List[str]
    stats: Optional[Dict[str, Any]] = None


# --------------------------
# Stage1：完整匹配任务（jobs）
# --------------------------

class StageStatsOut(BaseModel):
    candidates: int = 0
    matches: int = 0
    priority_matches: int = 0
    normal_matches: int = 0
    unmatched_students_after_stage: int = 0
    unmatched_volunteers_in_stage: int = 0


class FinalStatsOut(BaseModel):
    total_matches: int = 0
    unmatched_students_count: int = 0
    unmatched_volunteers_count: int = 0


class MatchSummaryOut(BaseModel):
    algorithm_version: str
    llm_enabled: bool = False
    filters: Dict[str, Any] = Field(default_factory=dict)
    input_counts: Dict[str, int] = Field(default_factory=dict)
    stage_stats: Dict[str, StageStatsOut] = Field(default_factory=dict)
    final_stats: FinalStatsOut = Field(default_factory=FinalStatsOut)
    unmatched_students: List[str] = Field(default_factory=list)
    unmatched_volunteers: List[str] = Field(default_factory=list)


class RunFullMatchOut(BaseModel):
    job_id: int
    status: str
    summary: MatchSummaryOut
    matches_count: int


class MatchJobListItemOut(BaseModel):
    id: int
    status: str
    algorithm_version: str
    llm_enabled: bool
    grade_stage_filter: Optional[int] = None
    created_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_matches: int = 0
    unmatched_students_count: int = 0
    unmatched_volunteers_count: int = 0
    summary: Dict[str, Any] = Field(default_factory=dict)


class MatchJobsListOut(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[MatchJobListItemOut]


class MatchJobDetailOut(BaseModel):
    job: Dict[str, Any]
    results: List[MatchPairOut]