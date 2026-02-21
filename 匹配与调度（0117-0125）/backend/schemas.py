# schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class ErrorDetail(BaseModel):
    code: str
    message: str


class StudentOut(BaseModel):
    """学生输出模型"""
    model_config = ConfigDict(from_attributes=True)
    
    seq_no: str  # 匹配模型：String
    name: str
    gender: str
    grade_stage: int
    mode: str
    subj1: str  # 匹配模型：String
    subj2: str
    subj3: str
    weakness_text: Optional[str] = None
    learning_style: Optional[str] = None
    interests_text: Optional[str] = None
    personality_text: Optional[str] = None
    social_worker_name: Optional[str] = None  # 匹配模型：允许 None
    social_worker_phone: Optional[str] = None  # 匹配模型：允许 None
    is_priority: bool
    special_needs_text: Optional[str] = None


class VolunteerOut(BaseModel):
    """志愿者输出模型"""
    model_config = ConfigDict(from_attributes=True)
    
    seq_no: str
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
    subj1: str  # 改为 String
    subj2: str
    subj3: str
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