from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# =========================
# 通用响应模型
# =========================

class MessageOut(BaseModel):
    message: str


class DeleteResponse(BaseModel):
    ok: bool = True
    deleted: int = 1
    seq_no: str
    entity: str


class RootResponse(BaseModel):
    name: str
    status: str
    version: str
    docs: str


# =========================
# 导入预览 / 提交
# =========================

class ImportPreviewRowOut(BaseModel):
    row_no: int
    data: Optional[dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)


class ImportPreviewStatsOut(BaseModel):
    total_rows: int = 0
    valid_rows: int = 0
    error_rows: int = 0
    duplicate_rows_in_file: int = 0


class ImportPreviewResponse(BaseModel):
    job_id: str
    entity: str  # students / volunteers

    stats: ImportPreviewStatsOut
    error_summary: list[dict[str, Any]] = Field(default_factory=list)

    # 为兼容旧前端命名，保留 preview 字段
    preview: List[ImportPreviewRowOut] = Field(default_factory=list)

    # 同时提供 rows 字段，后续新前端可直接用
    rows: List[ImportPreviewRowOut] = Field(default_factory=list)

    # 仅统计信息，不回传所有 valid_rows 原始数据给前端
    preview_limit: int = 50


class ImportCommitResponse(BaseModel):
    ok: bool = True
    entity: str  # students / volunteers
    job_id: str

    total_candidates: int = 0
    inserted: int = 0
    skipped_existing: int = 0

    # 额外信息
    message: str = ""


# =========================
# 学生 / 老师输出模型
# =========================

class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seq_no: str
    name: str
    gender: str

    stage_code: int
    tutoring_mode: str

    subj1: int
    subj2: int
    subj3: int

    student_profile: str
    learning_style: str
    interests: str
    personality: str

    social_worker_name: str
    social_worker_phone: str
    is_priority: bool
    special_need: str

    # 兼容旧前端字段名（可直接返回）
    grade_stage: int
    mode: str


class VolunteerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seq_no: str
    name: str
    gender: str

    student_no: str
    email: str
    department: str

    tutoring_mode: str
    match_mode: str
    joined_before: bool
    personality: str
    student_gender_requirement: str

    subj1: int
    subj2: int
    subj3: int

    stage_pref1: int
    stage_pref2: int
    stage_pref3: int

    capacity: int

    # 兼容旧前端可能使用的字段名
    mode: str


class PagedStudentsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[StudentOut]


class PagedVolunteersResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[VolunteerOut]