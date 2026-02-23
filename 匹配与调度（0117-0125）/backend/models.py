# models.py
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Float,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Student(Base):
    __tablename__ = "students"

    # 主键：seq_no - 改为 String，因为学号可能包含字母
    seq_no: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)  # M/F
    grade_stage: Mapped[int] = mapped_column(Integer, nullable=False)  # 1/2/3
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # online/offline/both

    # 科目：虽然存的是数字代码，但用 String 更灵活
    subj1: Mapped[str] = mapped_column(String(10), nullable=False)
    subj2: Mapped[str] = mapped_column(String(10), nullable=False)
    subj3: Mapped[str] = mapped_column(String(10), nullable=False)

    weakness_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    learning_style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interests_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    personality_text: Mapped[str | None] = mapped_column(String(200), nullable=True)

    social_worker_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    social_worker_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    special_needs_text: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Volunteer(Base):
    __tablename__ = "volunteers"

    seq_no: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)  # M/F

    student_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_major: Mapped[str | None] = mapped_column(String(128), nullable=True)

    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # online/offline/both
    match_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # direct/pre

    # 对学生性别要求：none/M/F
    gender_requirement: Mapped[str] = mapped_column(String(8), nullable=False, default="none")

    # 年级偏好（学段偏好）三列
    grade1: Mapped[int] = mapped_column(Integer, nullable=False)
    grade2: Mapped[int] = mapped_column(Integer, nullable=False)
    grade3: Mapped[int] = mapped_column(Integer, nullable=False)

    # 科目偏好三列
    subj1: Mapped[str] = mapped_column(String(10), nullable=False)
    subj2: Mapped[str] = mapped_column(String(10), nullable=False)
    subj3: Mapped[str] = mapped_column(String(10), nullable=False)

    # 容量：可带几个学生（默认 1）
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 教学风格（后续 DeepSeek）
    teaching_style_text: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # 是否参加过/其它（可扩展）
    participated_before: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MatchJob(Base):
    """
    Stage1：一次完整匹配任务（direct -> pre）对应一条记录
    """
    __tablename__ = "match_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/success/failed
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1_greedy_direct_then_pre")
    llm_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    grade_stage_filter: Mapped[int | None] = mapped_column(Integer, nullable=True)

    params_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchResult(Base):
    """
    Stage1：最终匹配结果明细（只存最终选中的 pair，不存全量候选）
    """
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("match_jobs.id"), index=True, nullable=False)

    stage: Mapped[str] = mapped_column(String(16), nullable=False)       # direct / pre
    round_type: Mapped[str] = mapped_column(String(16), nullable=False)  # priority / normal
    match_order: Mapped[int] = mapped_column(Integer, nullable=False)     # 本阶段选中顺序（1-based）

    student_seq_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    student_name_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    volunteer_seq_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    volunteer_name_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)

    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    base_score: Mapped[float] = mapped_column(Float, nullable=False)
    grade_score: Mapped[float] = mapped_column(Float, nullable=False)
    subject_score: Mapped[float] = mapped_column(Float, nullable=False)
    style_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    special_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    best_subject_raw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_subject_ids_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    best_subject_details_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())