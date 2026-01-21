from pydantic import BaseModel, Field
from typing import List, Optional


class ErrorDetail(BaseModel):
    code: str
    message: str


class StudentsListItem(BaseModel):
    seq_no: int
    name: str
    gender: str
    grade_stage: int
    mode: str
    subj1: int
    subj2: int
    subj3: int
    weakness_text: Optional[str] = None
    learning_style: Optional[str] = None
    interests_text: Optional[str] = None
    personality_text: Optional[str] = None
    social_worker_name: Optional[str] = None
    social_worker_phone: Optional[str] = None
    is_priority: bool
    special_needs_text: Optional[str] = None


class VolunteersListItem(BaseModel):
    seq_no: int
    name: str
    gender: str
    student_no: Optional[str] = None
    email: Optional[str] = None
    department_major: Optional[str] = None
    mode: str
    match_mode: str
    gender_requirement: str
    grade1: int
    grade2: int
    grade3: int
    subj1: int
    subj2: int
    subj3: int
    capacity: int
    teaching_style_text: Optional[str] = None
    participated_before: bool = False


class Paginated(BaseModel):
    total: int
    items: List


class ImportStats(BaseModel):
    total_rows: int
    valid_rows: int
    error_rows: int


class ImportPreviewResponse(BaseModel):
    job_id: str
    stats: ImportStats
    error_summary: list = Field(default_factory=list)
    preview: list = Field(default_factory=list)


class ImportCommitResponse(BaseModel):
    job_id: str
    inserted: int
