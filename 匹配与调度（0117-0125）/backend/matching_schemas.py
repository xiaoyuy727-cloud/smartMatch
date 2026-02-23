# backend/matching_schemas.py
from pydantic import BaseModel
from typing import List, Optional, Any


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

    # Stage2: 聚合主观分（仍保留）
    style_score: float
    # Stage2: 分维度主观分
    teaching_style_score: float = 0.0
    major_match_score: float = 0.0

    base_score: float
    special_penalty: float
    total_score: float

    best_subject_raw: int
    best_subject_ids: List[int]
    best_subject_details: List[BestSubjectDetail]

    # Stage2: LLM解释与状态
    llm_status: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_version_style: Optional[str] = None
    prompt_version_major: Optional[str] = None
    prompt_version_special: Optional[str] = None

    llm_reason_style: Optional[str] = None
    llm_reason_major: Optional[str] = None
    llm_reason_special: Optional[str] = None

    llm_confidence_style: Optional[float] = None
    llm_confidence_major: Optional[float] = None
    llm_confidence_special: Optional[float] = None


class MatchPreviewOut(BaseModel):
    total_candidates: int
    topk: List[CandidatePairOut]
    stats: Optional[dict] = None


class MatchPairOut(BaseModel):
    student_seq_no: str
    student_name: str
    volunteer_seq_no: str
    volunteer_name: str

    total_score: float
    base_score: float
    grade_score: float
    subject_score: float

    # Stage2
    style_score: float
    teaching_style_score: float = 0.0
    major_match_score: float = 0.0
    special_penalty: float = 0.0

    best_subject_raw: int
    best_subject_ids: List[int]
    best_subject_details: List[BestSubjectDetail]

    llm_status: Optional[str] = None
    llm_reason_style: Optional[str] = None
    llm_reason_major: Optional[str] = None
    llm_reason_special: Optional[str] = None
    llm_confidence_style: Optional[float] = None
    llm_confidence_major: Optional[float] = None
    llm_confidence_special: Optional[float] = None


class MatchRunOut(BaseModel):
    matches: List[MatchPairOut]
    unmatched_students: List[str]
    unmatched_volunteers: List[str]
    stats: Optional[dict] = None