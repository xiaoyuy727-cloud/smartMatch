from __future__ import annotations

import io
from collections import Counter
from typing import Any, Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Student, Volunteer
from validators import (
    validate_student_row,
    validate_volunteer_row,
)


def read_xlsx_rows(file_bytes: bytes) -> list[list[Any]]:
    """
    读取 xlsx 第一个 sheet，按无表头模式解析为二维列表。
    """
    try:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            header=None,
            sheet_name=0,
            engine="openpyxl",
            dtype=object,
        )
    except Exception as e:
        raise ValueError(f"无法读取xlsx文件: {e}") from e

    rows: list[list[Any]] = []
    for _, row in df.iterrows():
        rows.append(row.tolist())
    return rows


def _summarize_errors(preview_rows: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for r in preview_rows:
        for err in r.get("errors", []):
            counter[err] += 1
    return [{"error": k, "count": v} for k, v in counter.most_common(top_n)]


def _apply_file_duplicate_rule(validated_rows: list[dict[str, Any]]) -> None:
    """
    文件内序号重复：保留第一条，后续重复行标记错误并剔除 data（不参与 commit）。
    仅对 data 已成功解析的行处理。
    """
    seen: set[str] = set()
    for item in validated_rows:
        data = item.get("data")
        if not data:
            continue
        seq_no = str(data.get("seq_no", "")).strip()
        if not seq_no:
            continue
        if seq_no in seen:
            item["errors"].append("序号重复（文件内），按规则跳过（保留第一条）")
            item["data"] = None
        else:
            seen.add(seq_no)


def _build_preview(
    rows: list[list[Any]],
    entity: str,
    validator_func: Callable[[list[Any], int], dict[str, Any]],
    max_preview_rows: int = 50,
) -> dict[str, Any]:
    validated = []
    for idx, raw in enumerate(rows, start=1):
        result = validator_func(raw, idx)
        validated.append(result)

    # 文件内重复序号处理（保留第一条）
    _apply_file_duplicate_rule(validated)

    total_rows = len(validated)
    valid_rows = sum(1 for r in validated if r.get("data") is not None and not r.get("errors"))
    error_rows = total_rows - valid_rows
    duplicate_rows_in_file = sum(
        1 for r in validated if any("序号重复（文件内）" in e for e in r.get("errors", []))
    )

    preview_rows = []
    for r in validated[:max_preview_rows]:
        preview_rows.append(
            {
                "row_no": r["row_no"],
                "data": r.get("data"),
                "errors": r.get("errors", []),
            }
        )

    valid_data_rows = [r["data"] for r in validated if r.get("data") is not None and not r.get("errors")]

    return {
        "entity": entity,
        "stats": {
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "error_rows": error_rows,
            "duplicate_rows_in_file": duplicate_rows_in_file,
        },
        "preview": preview_rows,
        "rows": preview_rows,  # 为新前端保留同义字段
        "error_summary": _summarize_errors(validated),
        "valid_rows": valid_data_rows,  # 仅供后端 commit 使用，不直接回给前端
        "preview_limit": max_preview_rows,
    }


def preview_students_xlsx(file_bytes: bytes, max_preview_rows: int = 50) -> dict[str, Any]:
    rows = read_xlsx_rows(file_bytes)
    return _build_preview(rows, "students", validate_student_row, max_preview_rows=max_preview_rows)


def preview_volunteers_xlsx(file_bytes: bytes, max_preview_rows: int = 50) -> dict[str, Any]:
    rows = read_xlsx_rows(file_bytes)
    return _build_preview(rows, "volunteers", validate_volunteer_row, max_preview_rows=max_preview_rows)


def commit_students(db: Session, valid_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    按规则提交学生数据：
    - 数据库中序号已存在 -> 跳过
    """
    if not valid_rows:
        return {
            "entity": "students",
            "total_candidates": 0,
            "inserted": 0,
            "skipped_existing": 0,
        }

    seqs = [str(r["seq_no"]) for r in valid_rows]
    existing_seqs = set(
        db.scalars(select(Student.seq_no).where(Student.seq_no.in_(seqs))).all()
    )

    inserted = 0
    skipped_existing = 0

    for row in valid_rows:
        seq_no = str(row["seq_no"])
        if seq_no in existing_seqs:
            skipped_existing += 1
            continue

        obj = Student(
            seq_no=seq_no,
            name=row["name"],
            gender=row["gender"],
            stage_code=row["stage_code"],
            tutoring_mode=row["tutoring_mode"],
            subj1=row["subj1"],
            subj2=row["subj2"],
            subj3=row["subj3"],
            student_profile=row["student_profile"],
            learning_style=row["learning_style"],
            interests=row["interests"],
            personality=row["personality"],
            social_worker_name=row["social_worker_name"],
            social_worker_phone=row["social_worker_phone"],
            is_priority=row["is_priority"],
            special_need=row["special_need"],
        )
        db.add(obj)
        inserted += 1

    db.commit()

    return {
        "entity": "students",
        "total_candidates": len(valid_rows),
        "inserted": inserted,
        "skipped_existing": skipped_existing,
    }


def commit_volunteers(db: Session, valid_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    按规则提交志愿者数据：
    - 数据库中序号已存在 -> 跳过
    """
    if not valid_rows:
        return {
            "entity": "volunteers",
            "total_candidates": 0,
            "inserted": 0,
            "skipped_existing": 0,
        }

    seqs = [str(r["seq_no"]) for r in valid_rows]
    existing_seqs = set(
        db.scalars(select(Volunteer.seq_no).where(Volunteer.seq_no.in_(seqs))).all()
    )

    inserted = 0
    skipped_existing = 0

    for row in valid_rows:
        seq_no = str(row["seq_no"])
        if seq_no in existing_seqs:
            skipped_existing += 1
            continue

        obj = Volunteer(
            seq_no=seq_no,
            name=row["name"],
            gender=row["gender"],
            student_no=row["student_no"],
            email=row["email"],
            department=row["department"],
            tutoring_mode=row["tutoring_mode"],
            match_mode=row["match_mode"],
            joined_before=row["joined_before"],
            personality=row["personality"],
            student_gender_requirement=row["student_gender_requirement"],
            subj1=row["subj1"],
            subj2=row["subj2"],
            subj3=row["subj3"],
            stage_pref1=row["stage_pref1"],
            stage_pref2=row["stage_pref2"],
            stage_pref3=row["stage_pref3"],
            capacity=row["capacity"],
        )
        db.add(obj)
        inserted += 1

    db.commit()

    return {
        "entity": "volunteers",
        "total_candidates": len(valid_rows),
        "inserted": inserted,
        "skipped_existing": skipped_existing,
    }