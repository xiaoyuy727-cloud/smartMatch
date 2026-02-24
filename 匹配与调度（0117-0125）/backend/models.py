from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# =========================
# 基础数据表：学生 / 志愿者
# =========================

class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("seq_no", name="uq_students_seq_no"),
        Index("ix_students_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Excel 字段（无表头固定顺序）
    seq_no: Mapped[str] = mapped_column(String(64), nullable=False)  # 序号（作为业务唯一键）
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)  # M/F
    stage_code: Mapped[int] = mapped_column(Integer, nullable=False)  # 1/2/3
    tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # offline/online/both

    subj1: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subj2: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subj3: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    student_profile: Mapped[str] = mapped_column(Text, nullable=False, default="无")       # 学生情况描述
    learning_style: Mapped[str] = mapped_column(Text, nullable=False, default="无")        # 学习风格描述
    interests: Mapped[str] = mapped_column(Text, nullable=False, default="无")             # 兴趣爱好
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="无")           # 学生性格

    social_worker_name: Mapped[str] = mapped_column(String(128), nullable=False, default="无")
    social_worker_phone: Mapped[str] = mapped_column(String(64), nullable=False, default="无")

    is_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    special_need: Mapped[str] = mapped_column(Text, nullable=False, default="无")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Volunteer(Base):
    __tablename__ = "volunteers"
    __table_args__ = (
        UniqueConstraint("seq_no", name="uq_volunteers_seq_no"),
        Index("ix_volunteers_name", "name"),
        Index("ix_volunteers_match_mode", "match_mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    seq_no: Mapped[str] = mapped_column(String(64), nullable=False)  # 序号（业务唯一键）
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)  # M/F

    student_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")       # 学号
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")            # 学邮
    department: Mapped[str] = mapped_column(String(255), nullable=False, default="无")     # 院系

    tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # offline/online/both
    match_mode: Mapped[str] = mapped_column(String(16), nullable=False)      # direct/pre

    joined_before: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)    # 是否参加过
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="无")            # 个人性格
    student_gender_requirement: Mapped[str] = mapped_column(String(1), nullable=False, default="N")  # F/M/N

    subj1: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subj2: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subj3: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    stage_pref1: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_pref2: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_pref3: Mapped[int] = mapped_column(Integer, nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 本期按1使用

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ==========================================
# 匹配结果相关（本批不使用，但先建好最终结构）
# ==========================================

class MatchPairScoreDetail(Base):
    """
    所有实际参与计算的合法 pair 打分明细（按阶段落库）
    phase: direct / pre
    """
    __tablename__ = "match_pair_score_details"
    __table_args__ = (
        Index("ix_pair_scores_phase", "phase"),
        Index("ix_pair_scores_student_seq", "student_seq"),
        Index("ix_pair_scores_teacher_seq", "teacher_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # direct/pre
    student_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    student_name: Mapped[str] = mapped_column(String(128), nullable=False)
    teacher_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    teacher_name: Mapped[str] = mapped_column(String(128), nullable=False)

    student_tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    teacher_tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    student_is_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    teacher_match_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    # 客观分
    grade_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    subject_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    best_subject_raw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # DS 主观匹配（40）
    ds_subjective_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ds_subjective_reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_subjective_reason_raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_subjective_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    ds_subjective_error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_subjective_cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ds_subjective_input_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # DS 特殊需求惩罚（20）
    ds_special_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ds_special_reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_special_reason_raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_special_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    ds_special_error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_special_cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ds_special_input_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    selected_in_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    not_selected_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FinalMatchResult(Base):
    __tablename__ = "final_match_results"
    __table_args__ = (
        Index("ix_final_results_phase", "phase"),
        Index("ix_final_results_student_seq", "student_seq"),
        Index("ix_final_results_teacher_seq", "teacher_seq"),
        UniqueConstraint("student_seq", name="uq_final_results_student_seq"),
        UniqueConstraint("teacher_seq", name="uq_final_results_teacher_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # direct/pre

    student_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    student_name: Mapped[str] = mapped_column(String(128), nullable=False)
    teacher_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    teacher_name: Mapped[str] = mapped_column(String(128), nullable=False)

    tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    teacher_match_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="")

    grade_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    subject_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ds_subjective_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ds_special_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    ds_subjective_reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ds_special_reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UnmatchedStudent(Base):
    __tablename__ = "unmatched_students"
    __table_args__ = (
        UniqueConstraint("student_seq", name="uq_unmatched_students_student_seq"),
        Index("ix_unmatched_students_student_seq", "student_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    student_name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    stage_code: Mapped[int] = mapped_column(Integer, nullable=False)
    tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    is_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class UnusedVolunteer(Base):
    __tablename__ = "unused_volunteers"
    __table_args__ = (
        UniqueConstraint("teacher_seq", name="uq_unused_volunteers_teacher_seq"),
        Index("ix_unused_volunteers_teacher_seq", "teacher_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    teacher_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    teacher_name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    tutoring_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    match_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DSScoreCache(Base):
    """
    DS 评分缓存（数据库缓存）
    键建议：student_seq + teacher_seq + score_type + input_hash
    score_type: subjective / special
    """
    __tablename__ = "ds_score_cache"
    __table_args__ = (
        UniqueConstraint(
            "student_seq", "teacher_seq", "score_type", "input_hash",
            name="uq_ds_score_cache_pair_type_hash"
        ),
        Index("ix_ds_score_cache_pair", "student_seq", "teacher_seq"),
        Index("ix_ds_score_cache_score_type", "score_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    teacher_seq: Mapped[str] = mapped_column(String(64), nullable=False)
    score_type: Mapped[str] = mapped_column(String(32), nullable=False)  # subjective/special
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    score_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason_raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )