from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from ds_scoring_service import DSScoringService
from matching_rules import (
    calc_best_subject_raw,
    calc_grade_score,
    calc_subject_score_from_best_raw,
    calc_total_score,
    is_legal_pair,
    pair_sort_key,
)
from models import MatchPairScoreDetail, Student, Volunteer


@dataclass
class ScoredPair:
    student: Student
    teacher: Volunteer
    phase: str

    grade_score: float
    best_subject_raw: int
    subject_score: float

    ds_subjective_score: float
    ds_subjective_reason_summary: str
    ds_subjective_reason_raw: str
    ds_subjective_status: str
    ds_subjective_error_message: str
    ds_subjective_cache_hit: bool
    ds_subjective_input_hash: str

    ds_special_penalty: float
    ds_special_reason_summary: str
    ds_special_reason_raw: str
    ds_special_status: str
    ds_special_error_message: str
    ds_special_cache_hit: bool
    ds_special_input_hash: str

    total_score: float

    # 对应落库对象（创建后填充）
    db_obj: MatchPairScoreDetail | None = None


class MatchingService:
    def __init__(self) -> None:
        self.ds = DSScoringService()

    def build_scored_pairs(
        self,
        db: Session,
        phase: str,
        students: List[Student],
        teachers: List[Volunteer],
    ) -> List[ScoredPair]:
        scored: List[ScoredPair] = []

        for s in students:
            for t in teachers:
                if not is_legal_pair(
                    student_gender=s.gender,
                    student_mode=s.tutoring_mode,
                    teacher_mode=t.tutoring_mode,
                    teacher_student_gender_requirement=t.student_gender_requirement,
                ):
                    continue

                grade_score = calc_grade_score(s.stage_code, t.stage_pref1, t.stage_pref2, t.stage_pref3)

                best_raw = calc_best_subject_raw(
                    s.subj1, s.subj2, s.subj3,
                    t.subj1, t.subj2, t.subj3
                )
                subject_score = calc_subject_score_from_best_raw(best_raw)

                subj_res = self.ds.score_subjective(db, s, t)
                spec_res = self.ds.score_special_penalty(db, s, t)

                total = calc_total_score(
                    grade_score=grade_score,
                    subject_score=subject_score,
                    ds_subjective_score=subj_res.score_value,
                    ds_special_penalty=spec_res.score_value,
                )

                sp = ScoredPair(
                    student=s,
                    teacher=t,
                    phase=phase,
                    grade_score=grade_score,
                    best_subject_raw=best_raw,
                    subject_score=subject_score,
                    ds_subjective_score=subj_res.score_value,
                    ds_subjective_reason_summary=subj_res.reason_summary,
                    ds_subjective_reason_raw=subj_res.reason_raw,
                    ds_subjective_status=subj_res.status,
                    ds_subjective_error_message=subj_res.error_message,
                    ds_subjective_cache_hit=subj_res.cache_hit,
                    ds_subjective_input_hash=subj_res.input_hash,
                    ds_special_penalty=spec_res.score_value,
                    ds_special_reason_summary=spec_res.reason_summary,
                    ds_special_reason_raw=spec_res.reason_raw,
                    ds_special_status=spec_res.status,
                    ds_special_error_message=spec_res.error_message,
                    ds_special_cache_hit=spec_res.cache_hit,
                    ds_special_input_hash=spec_res.input_hash,
                    total_score=total,
                )
                scored.append(sp)

        # 排序：total 降序；同分 teacher_seq 小优先；再 student_seq 做稳定键
        scored.sort(key=lambda x: pair_sort_key(x.total_score, x.teacher.seq_no, x.student.seq_no))
        return scored

    def persist_pair_details(self, db: Session, pairs: List[ScoredPair]) -> None:
        objs: List[MatchPairScoreDetail] = []
        for p in pairs:
            obj = MatchPairScoreDetail(
                phase=p.phase,
                student_seq=p.student.seq_no,
                student_name=p.student.name,
                teacher_seq=p.teacher.seq_no,
                teacher_name=p.teacher.name,
                student_tutoring_mode=p.student.tutoring_mode,
                teacher_tutoring_mode=p.teacher.tutoring_mode,
                student_is_priority=bool(p.student.is_priority),
                teacher_match_mode=p.teacher.match_mode,
                grade_score=float(p.grade_score),
                subject_score=float(p.subject_score),
                best_subject_raw=float(p.best_subject_raw),
                ds_subjective_score=float(p.ds_subjective_score),
                ds_subjective_reason_summary=p.ds_subjective_reason_summary or "",
                ds_subjective_reason_raw=p.ds_subjective_reason_raw or "",
                ds_subjective_status=p.ds_subjective_status or "unknown",
                ds_subjective_error_message=p.ds_subjective_error_message or "",
                ds_subjective_cache_hit=bool(p.ds_subjective_cache_hit),
                ds_subjective_input_hash=p.ds_subjective_input_hash or "",
                ds_special_penalty=float(p.ds_special_penalty),
                ds_special_reason_summary=p.ds_special_reason_summary or "",
                ds_special_reason_raw=p.ds_special_reason_raw or "",
                ds_special_status=p.ds_special_status or "unknown",
                ds_special_error_message=p.ds_special_error_message or "",
                ds_special_cache_hit=bool(p.ds_special_cache_hit),
                ds_special_input_hash=p.ds_special_input_hash or "",
                total_score=float(p.total_score),
                selected_in_final=False,
                not_selected_reason="",
            )
            p.db_obj = obj
            objs.append(obj)

        if objs:
            db.add_all(objs)
            db.commit()

    def select_matches_two_pass(self, pairs: List[ScoredPair]) -> Tuple[List[ScoredPair], set[str], set[str]]:
        matched_students: set[str] = set()
        matched_teachers: set[str] = set()
        selected: List[ScoredPair] = []

        # 第一轮：优先学生
        for p in pairs:
            if not p.student.is_priority:
                continue  # 保留到第二轮
            if p.student.seq_no in matched_students:
                continue
            if p.teacher.seq_no in matched_teachers:
                continue
            matched_students.add(p.student.seq_no)
            matched_teachers.add(p.teacher.seq_no)
            selected.append(p)

        # 第二轮：普通学生（包含第一轮跳过的非优先 pair）
        for p in pairs:
            if p.student.seq_no in matched_students:
                continue
            if p.teacher.seq_no in matched_teachers:
                continue
            matched_students.add(p.student.seq_no)
            matched_teachers.add(p.teacher.seq_no)
            selected.append(p)

        return selected, matched_students, matched_teachers

    def mark_selected_in_db(self, db: Session, selected: List[ScoredPair]) -> None:
        # 将被选中的pair在明细表中标记 selected_in_final=True
        for p in selected:
            if p.db_obj is not None:
                p.db_obj.selected_in_final = True
                db.add(p.db_obj)
        db.commit()

    def run_phase(
        self,
        db: Session,
        phase: str,
        students: List[Student],
        teachers: List[Volunteer],
    ) -> Tuple[List[ScoredPair], List[Student], List[Volunteer], List[ScoredPair]]:
        """
        返回：
        - selected_pairs: 本阶段选中的配对
        - remaining_students
        - remaining_teachers
        - all_scored_pairs: 本阶段所有合法pair（已打分、已落库）
        """
        scored_pairs = self.build_scored_pairs(db, phase, students, teachers)
        self.persist_pair_details(db, scored_pairs)

        selected, matched_student_seqs, matched_teacher_seqs = self.select_matches_two_pass(scored_pairs)
        self.mark_selected_in_db(db, selected)

        remaining_students = [s for s in students if s.seq_no not in matched_student_seqs]
        remaining_teachers = [t for t in teachers if t.seq_no not in matched_teacher_seqs]

        return selected, remaining_students, remaining_teachers, scored_pairs