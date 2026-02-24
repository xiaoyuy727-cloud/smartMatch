from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import FinalMatchResult, MatchPairScoreDetail, UnmatchedStudent, UnusedVolunteer


class MatchingStore:
    """
    当前结果查询（无历史任务）
    """

    def list_final_results(self, db: Session, offset: int = 0, limit: int = 200):
        stmt = select(FinalMatchResult).order_by(FinalMatchResult.total_score.desc())
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(stmt.offset(offset).limit(limit)).all()
        return total, items

    def list_pair_details(
        self,
        db: Session,
        offset: int = 0,
        limit: int = 200,
        phase: Optional[str] = None,
        selected_in_final: Optional[bool] = None,
        student_seq: Optional[str] = None,
        teacher_seq: Optional[str] = None,
    ):
        stmt = select(MatchPairScoreDetail).order_by(MatchPairScoreDetail.total_score.desc())

        if phase:
            stmt = stmt.where(MatchPairScoreDetail.phase == phase)
        if selected_in_final is not None:
            stmt = stmt.where(MatchPairScoreDetail.selected_in_final == selected_in_final)
        if student_seq:
            stmt = stmt.where(MatchPairScoreDetail.student_seq == student_seq)
        if teacher_seq:
            stmt = stmt.where(MatchPairScoreDetail.teacher_seq == teacher_seq)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(stmt.offset(offset).limit(limit)).all()
        return total, items

    def list_unmatched_students(self, db: Session, offset: int = 0, limit: int = 200):
        stmt = select(UnmatchedStudent).order_by(UnmatchedStudent.id.asc())
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(stmt.offset(offset).limit(limit)).all()
        return total, items

    def list_unused_volunteers(self, db: Session, offset: int = 0, limit: int = 200):
        stmt = select(UnusedVolunteer).order_by(UnusedVolunteer.id.asc())
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(stmt.offset(offset).limit(limit)).all()
        return total, items