from pydantic import BaseModel
from typing import List, Optional


class BestSubjectDetail(BaseModel):
    subject_id: int
    student_rank: int
    student_weight: int
    teacher_rank: int
    teacher_weight: int
    product: int  # 0..9


class CandidatePairOut(BaseModel):
    student_seq_no: int
    student_name: str
    student_is_priority: bool

    volunteer_seq_no: int
    volunteer_name: str
    volunteer_match_mode: str
    volunteer_capacity: int

    is_legal: bool
    illegal_reason: Optional[str] = None

    grade_score: float
    subject_score: float
    style_score: float
    base_score: float

    special_penalty: float
    total_score: float

    best_subject_raw: int
    best_subject_ids: List[int]
    best_subject_details: List[BestSubjectDetail]


class MatchPreviewOut(BaseModel):
    total_candidates: int
    topk: List[CandidatePairOut]


class MatchPairOut(BaseModel):
    student_seq_no: int
    student_name: str
    volunteer_seq_no: int
    volunteer_name: str

    total_score: float
    base_score: float
    grade_score: float
    subject_score: float
    style_score: float
    special_penalty: float

    best_subject_raw: int
    best_subject_ids: List[int]
    best_subject_details: List[BestSubjectDetail]


class MatchRunOut(BaseModel):
    matches: List[MatchPairOut]
    unmatched_students: List[int]
    unmatched_volunteers: List[int]
