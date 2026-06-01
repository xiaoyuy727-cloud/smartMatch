from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from matching_service import MatchingService, ScoredPair
from models import (
    FinalMatchResult,
    MatchPairScoreDetail,
    Student,
    UnmatchedStudent,
    UnusedVolunteer,
    Volunteer,
)


class MatchingOrchestrator:
    """
    自动完整匹配：
    - 清空旧结果（不清空 DS 缓存）
    - direct 阶段：所有学生 × direct老师（合法pair打分 + 两轮匹配）
    - 若仍有学生：pre 阶段：剩余学生 × pre老师（合法pair打分 + 两轮匹配）
    - 落库：
        - 合法pair打分明细（MatchPairScoreDetail）
        - 最终匹配结果（FinalMatchResult）
        - 未匹配学生（UnmatchedStudent）
        - 未使用老师（UnusedVolunteer）
    """

    def __init__(self) -> None:
        self.service = MatchingService()

    def clear_old_results(self, db: Session) -> None:
        db.execute(delete(MatchPairScoreDetail))
        db.execute(delete(FinalMatchResult))
        db.execute(delete(UnmatchedStudent))
        db.execute(delete(UnusedVolunteer))
        db.commit()

    def _persist_final_results(self, db: Session, selected: List[ScoredPair]) -> None:
        objs: List[FinalMatchResult] = []
        for p in selected:
            objs.append(
                FinalMatchResult(
                    phase=p.phase,
                    student_seq=p.student.seq_no,
                    student_name=p.student.name,
                    teacher_seq=p.teacher.seq_no,
                    teacher_name=p.teacher.name,
                    tutoring_mode=p.teacher.tutoring_mode,
                    teacher_match_mode=p.teacher.match_mode,
                    grade_score=float(p.grade_score),
                    subject_score=float(p.subject_score),
                    ds_subjective_score=float(p.ds_subjective_score),
                    ds_special_penalty=float(p.ds_special_penalty),
                    total_score=float(p.total_score),
                    ds_subjective_reason_summary=p.ds_subjective_reason_summary or "",
                    ds_special_reason_summary=p.ds_special_reason_summary or "",
                )
            )
        if objs:
            db.add_all(objs)
            db.commit()

    def _persist_unmatched_students(self, db: Session, students: List[Student], reason: str = "") -> None:
        objs: List[UnmatchedStudent] = []
        for s in students:
            objs.append(
                UnmatchedStudent(
                    student_seq=s.seq_no,
                    student_name=s.name,
                    gender=s.gender,
                    stage_code=s.stage_code,
                    tutoring_mode=s.tutoring_mode,
                    is_priority=bool(s.is_priority),
                    reason_summary=reason or "未匹配到老师",
                )
            )
        if objs:
            db.add_all(objs)
            db.commit()

    def _persist_unused_volunteers(self, db: Session, volunteers: List[Volunteer], reason: str = "") -> None:
        objs: List[UnusedVolunteer] = []
        for v in volunteers:
            objs.append(
                UnusedVolunteer(
                    teacher_seq=v.seq_no,
                    teacher_name=v.name,
                    gender=v.gender,
                    tutoring_mode=v.tutoring_mode,
                    match_mode=v.match_mode,
                    reason_summary=reason or "未被匹配到学生",
                )
            )
        if objs:
            db.add_all(objs)
            db.commit()

    def run_full_match(self, db: Session) -> dict:
        self.clear_old_results(db)

        students = db.scalars(select(Student).order_by(Student.id.asc())).all()
        volunteers = db.scalars(select(Volunteer).order_by(Volunteer.id.asc())).all()

        direct_teachers = [v for v in volunteers if (v.match_mode or "").lower() == "direct"]
        pre_teachers = [v for v in volunteers if (v.match_mode or "").lower() == "pre"]

        all_selected: List[ScoredPair] = []

        # phase direct
        direct_selected, remaining_students, remaining_direct_teachers, _ = self.service.run_phase(
            db=db, phase="direct", students=students, teachers=direct_teachers
        )
        all_selected.extend(direct_selected)

        # phase pre (仅剩余学生)
        pre_selected: List[ScoredPair] = []
        remaining_pre_teachers = pre_teachers
        if remaining_students:
            pre_selected, remaining_students, remaining_pre_teachers, _ = self.service.run_phase(
                db=db, phase="pre", students=remaining_students, teachers=pre_teachers
            )
            all_selected.extend(pre_selected)

        # 最终结果落库
        self._persist_final_results(db, all_selected)

        # 未匹配学生落库
        self._persist_unmatched_students(db, remaining_students, reason="direct与pre阶段均未匹配成功")

        # 未使用老师：从所有老师中扣掉已匹配老师
        matched_teacher_seqs = {p.teacher.seq_no for p in all_selected}
        unused_volunteers = [v for v in volunteers if v.seq_no not in matched_teacher_seqs]
        self._persist_unused_volunteers(db, unused_volunteers, reason="未被匹配选中")

        summary = {
            "ok": True,
            "cleared_old_results": True,
            "total_students": len(students),
            "total_volunteers": len(volunteers),
            "direct_volunteers": len(direct_teachers),
            "pre_volunteers": len(pre_teachers),
            "direct_matched": len(direct_selected),
            "pre_matched": len(pre_selected),
            "total_matched": len(all_selected),
            "unmatched_students": len(remaining_students),
            "unused_volunteers": len(unused_volunteers),
            "message": (
                f"匹配完成：学生{len(students)}，老师{len(volunteers)}；"
                f"direct匹配{len(direct_selected)}，pre匹配{len(pre_selected)}；"
                f"未匹配学生{len(remaining_students)}，未使用老师{len(unused_volunteers)}。"
            ),
        }
        return summary