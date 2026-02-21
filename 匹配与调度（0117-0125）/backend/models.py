# models.py
from sqlalchemy import String, Integer, Boolean
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
    subj1: Mapped[str] = mapped_column(String(10), nullable=False)  # 改为 String
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

    seq_no: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)  # 改为 String

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
    grade1: Mapped[int] = mapped_column(Integer, nullable=False)  # 1/2/3
    grade2: Mapped[int] = mapped_column(Integer, nullable=False)
    grade3: Mapped[int] = mapped_column(Integer, nullable=False)

    # 科目偏好三列 - 改为 String
    subj1: Mapped[str] = mapped_column(String(10), nullable=False)
    subj2: Mapped[str] = mapped_column(String(10), nullable=False)
    subj3: Mapped[str] = mapped_column(String(10), nullable=False)

    # 容量：可带几个学生（默认 1）
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 教学风格（后续 DeepSeek）
    teaching_style_text: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # 是否参加过/其它（可扩展）
    participated_before: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)