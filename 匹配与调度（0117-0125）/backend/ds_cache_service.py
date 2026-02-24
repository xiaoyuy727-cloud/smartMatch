from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import DSScoreCache


class DSCacheService:
    """
    DS 评分缓存（DB）
    只把 status=success 或 status=skipped 作为可直接命中使用的缓存。
    """

    def get(
        self,
        db: Session,
        student_seq: str,
        teacher_seq: str,
        score_type: str,
        input_hash: str,
    ) -> Optional[DSScoreCache]:
        stmt = select(DSScoreCache).where(
            DSScoreCache.student_seq == student_seq,
            DSScoreCache.teacher_seq == teacher_seq,
            DSScoreCache.score_type == score_type,
            DSScoreCache.input_hash == input_hash,
        )
        return db.scalar(stmt)

    def get_usable(
        self,
        db: Session,
        student_seq: str,
        teacher_seq: str,
        score_type: str,
        input_hash: str,
    ) -> Optional[DSScoreCache]:
        obj = self.get(db, student_seq, teacher_seq, score_type, input_hash)
        if not obj:
            return None
        if obj.status in {"success", "skipped"}:
            return obj
        return None

    def upsert(
        self,
        db: Session,
        student_seq: str,
        teacher_seq: str,
        score_type: str,
        input_hash: str,
        score_value: float,
        reason_summary: str,
        reason_raw: str,
        status: str,
        error_message: str = "",
    ) -> DSScoreCache:
        obj = self.get(db, student_seq, teacher_seq, score_type, input_hash)
        if obj:
            obj.score_value = float(score_value)
            obj.reason_summary = reason_summary or ""
            obj.reason_raw = reason_raw or ""
            obj.status = status
            obj.error_message = error_message or ""
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj

        obj = DSScoreCache(
            student_seq=student_seq,
            teacher_seq=teacher_seq,
            score_type=score_type,
            input_hash=input_hash,
            score_value=float(score_value),
            reason_summary=reason_summary or "",
            reason_raw=reason_raw or "",
            status=status,
            error_message=error_message or "",
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj