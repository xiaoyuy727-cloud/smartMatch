from __future__ import annotations
import pandas as pd
from typing import Any, Dict, List, Tuple
import uuid

from validators import validate_student, validate_volunteer

STUDENT_COLUMNS = [
    "seq_no", "name", "gender", "grade_stage", "mode",
    "subj1", "subj2", "subj3",
    "weakness_text", "learning_style", "interests_text", "personality_text",
    "social_worker_name", "social_worker_phone", "is_priority", "special_needs_text",
]

VOLUNTEER_COLUMNS = [
    "seq_no", "name", "gender", "student_no", "email", "department_major",
    "mode", "match_mode", "gender_requirement",  # gender_requirement 保留
    "grade1", "grade2", "grade3",
    "subj1", "subj2", "subj3",
    "capacity", "style_text",  # 改为 style_text 而不是 teaching_style_text
    "has_participated_before",  # 改为 has_participated_before 而不是 participated_before
]

def parse_excel_to_rows(file_bytes: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """解析Excel文件为行数据 - 修复bytes类型问题"""
    # 将 bytes 转换为 BytesIO 对象
    import io
    file_obj = io.BytesIO(file_bytes)
    
    # 使用文件对象读取Excel
    df = pd.read_excel(file_obj)
    cols = [str(c).strip() for c in df.columns.tolist()]
    df.columns = cols
    rows = df.to_dict(orient="records")
    return cols, rows


def _missing_columns(actual_cols: List[str], required_cols: List[str]) -> List[str]:
    aset = set(actual_cols)
    return [c for c in required_cols if c not in aset]


def preview_students(file_bytes: bytes, strict: bool, max_preview_rows: int = 50):
    cols, rows = parse_excel_to_rows(file_bytes)
    miss = _missing_columns(cols, STUDENT_COLUMNS)
    if miss:
        return None, {
            "code": "MISSING_COLUMNS",
            "message": f"缺少列: {miss}",
        }

    cleaned: List[Dict[str, Any]] = []
    errors_by_row: List[Dict[str, Any]] = []

    for idx, r in enumerate(rows):
        row = {k: r.get(k) for k in STUDENT_COLUMNS}
        c, errs = validate_student(row)
        if errs:
            errors_by_row.append({"row_index": idx + 2, "errors": errs})  # +2: header + 1-based
        cleaned.append(c)

    total = len(rows)
    err_rows = len(errors_by_row)
    valid = total - err_rows

    job_id = f"stu_{uuid.uuid4().hex[:10]}"
    preview = cleaned[:max_preview_rows]

    error_summary = errors_by_row[: min(len(errors_by_row), 50)]
    result = {
        "job_id": job_id,
        "stats": {"total_rows": total, "valid_rows": valid, "error_rows": err_rows},
        "error_summary": error_summary,
        "preview": preview,
        "strict": strict,
        "rows_cleaned": cleaned,
        "errors_by_row": errors_by_row,
    }
    return result, None


def preview_volunteers(file_bytes: bytes, strict: bool, max_preview_rows: int = 50):
    cols, rows = parse_excel_to_rows(file_bytes)
    miss = _missing_columns(cols, VOLUNTEER_COLUMNS)
    if miss:
        return None, {
            "code": "MISSING_COLUMNS",
            "message": f"缺少列: {miss}",
        }

    cleaned: List[Dict[str, Any]] = []
    errors_by_row: List[Dict[str, Any]] = []

    for idx, r in enumerate(rows):
        row = {k: r.get(k) for k in VOLUNTEER_COLUMNS}
        c, errs = validate_volunteer(row)
        if errs:
            errors_by_row.append({"row_index": idx + 2, "errors": errs})
        cleaned.append(c)

    total = len(rows)
    err_rows = len(errors_by_row)
    valid = total - err_rows

    job_id = f"vol_{uuid.uuid4().hex[:10]}"
    preview = cleaned[:max_preview_rows]

    error_summary = errors_by_row[: min(len(errors_by_row), 50)]
    result = {
        "job_id": job_id,
        "stats": {"total_rows": total, "valid_rows": valid, "error_rows": err_rows},
        "error_summary": error_summary,
        "preview": preview,
        "strict": strict,
        "rows_cleaned": cleaned,
        "errors_by_row": errors_by_row,
    }
    return result, None

def parse_excel(file) -> pd.DataFrame:
    """兼容main.py调用的函数"""
    df = pd.read_excel(file)
    # 清理列名
    df.columns = [str(c).strip() for c in df.columns]
    return df

def preview_import(df, data_type, max_preview_rows=50):
    """兼容main.py调用的预览函数"""
    if data_type == "students":
        # 将DataFrame转换为bytes
        import io
        bytes_io = io.BytesIO()
        df.to_excel(bytes_io, index=False)
        bytes_io.seek(0)
        
        result, error = preview_students(bytes_io.read(), True, max_preview_rows)
        if error:
            return {"fatal_error": error}
        
        # 转换为preview_import期望的格式
        return {
            "stats": result["stats"],
            "columns": list(df.columns),
            "preview": result["preview"],
            "error_summary": result["error_summary"],
            "all_rows": [
                {"data": row, "errors": []} 
                for row in result["rows_cleaned"]
            ]
        }
    else:
        # volunteers类似处理
        import io
        bytes_io = io.BytesIO()
        df.to_excel(bytes_io, index=False)
        bytes_io.seek(0)
        
        result, error = preview_volunteers(bytes_io.read(), True, max_preview_rows)
        if error:
            return {"fatal_error": error}
        
        return {
            "stats": result["stats"],
            "columns": list(df.columns),
            "preview": result["preview"],
            "error_summary": result["error_summary"],
            "all_rows": [
                {"data": row, "errors": []} 
                for row in result["rows_cleaned"]
            ]
        }