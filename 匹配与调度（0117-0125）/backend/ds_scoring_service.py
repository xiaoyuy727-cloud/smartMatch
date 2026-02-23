# backend/ds_scoring_service.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from ds_client import DeepSeekClient
from ds_prompt_templates import (
    style_match_prompt,
    major_match_prompt,
    special_needs_prompt,
    PROMPT_VERSION_STYLE,
    PROMPT_VERSION_MAJOR,
    PROMPT_VERSION_SPECIAL,
)


def _clip(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _to_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _extract_json_obj(text: str) -> Dict[str, Any]:
    """
    尽量鲁棒地从文本中提取 JSON object。
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")

    # 1) 直接 parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2) 提取第一个 {...}
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        snippet = m.group(0)
        obj = json.loads(snippet)
        if isinstance(obj, dict):
            return obj

    raise ValueError("cannot parse JSON object")


@dataclass
class DimensionResult:
    ok: bool
    status: str
    score: float | None = None
    penalty: float | None = None
    confidence: float = 0.0
    reason: str = ""
    rule_checks: list[str] | None = None
    elapsed_ms: int = 0
    raw_text: str = ""
    error: str | None = None


def _parse_score_result(raw_text: str, score_min: float, score_max: float) -> DimensionResult:
    obj = _extract_json_obj(raw_text)
    score = _clip(_to_float(obj.get("score"), 0.0), score_min, score_max)
    conf = _clip(_to_float(obj.get("confidence"), 0.0), 0.0, 1.0)
    reason = str(obj.get("reason", "") or "")[:300]
    checks = obj.get("rule_checks", [])
    if not isinstance(checks, list):
        checks = []
    checks = [str(x)[:60] for x in checks[:10]]
    return DimensionResult(
        ok=True,
        status="ok",
        score=score,
        confidence=conf,
        reason=reason,
        rule_checks=checks,
        raw_text=raw_text,
    )


def _parse_penalty_result(raw_text: str, penalty_min: float, penalty_max: float) -> DimensionResult:
    obj = _extract_json_obj(raw_text)
    penalty = _clip(_to_float(obj.get("penalty"), 0.0), penalty_min, penalty_max)
    conf = _clip(_to_float(obj.get("confidence"), 0.0), 0.0, 1.0)
    reason = str(obj.get("reason", "") or "")[:300]
    checks = obj.get("rule_checks", [])
    if not isinstance(checks, list):
        checks = []
    checks = [str(x)[:60] for x in checks[:10]]
    return DimensionResult(
        ok=True,
        status="ok",
        penalty=penalty,
        confidence=conf,
        reason=reason,
        rule_checks=checks,
        raw_text=raw_text,
    )


def _fallback_score(reason: str) -> DimensionResult:
    return DimensionResult(
        ok=False,
        status="fallback",
        score=0.0,
        confidence=0.0,
        reason=reason,
        rule_checks=[],
        error=reason,
    )


def _fallback_penalty(reason: str) -> DimensionResult:
    return DimensionResult(
        ok=False,
        status="fallback",
        penalty=0.0,
        confidence=0.0,
        reason=reason,
        rule_checks=[],
        error=reason,
    )


def _call_score_dimension(client: DeepSeekClient, prompt_pack: Dict[str, str], kind: str) -> DimensionResult:
    resp = client.chat_json(prompt_pack["system"], prompt_pack["user"])
    if not resp.ok:
        return _fallback_score(f"{kind} 调用失败: {resp.error}") if kind != "special" else _fallback_penalty(f"{kind} 调用失败: {resp.error}")

    try:
        if kind == "style":
            dr = _parse_score_result(resp.content, 0.0, 20.0)
        elif kind == "major":
            dr = _parse_score_result(resp.content, 0.0, 20.0)
        else:
            dr = _parse_penalty_result(resp.content, -20.0, 0.0)
        dr.elapsed_ms = resp.elapsed_ms
        dr.raw_text = resp.content
        return dr
    except Exception as e:
        return _fallback_score(f"{kind} 解析失败: {e}") if kind != "special" else _fallback_penalty(f"{kind} 解析失败: {e}")


def score_subjective_pair(
    student: Dict,
    volunteer: Dict,
    client: DeepSeekClient,
) -> Dict[str, Any]:
    """
    返回用于并入 score / 落库 / 前端展示的结构化结果。
    """
    style_p = style_match_prompt(student, volunteer)
    major_p = major_match_prompt(student, volunteer)
    special_p = special_needs_prompt(student, volunteer)

    rs_style = _call_score_dimension(client, style_p, "style")
    rs_major = _call_score_dimension(client, major_p, "major")
    rs_special = _call_score_dimension(client, special_p, "special")

    teaching_style_score = float(rs_style.score or 0.0)
    major_match_score = float(rs_major.score or 0.0)
    special_penalty = float(rs_special.penalty or 0.0)
    style_score = teaching_style_score + major_match_score  # 与 Stage1 style_score 字段兼容

    ok_count = sum(1 for x in [rs_style, rs_major, rs_special] if x.ok)
    if ok_count == 3:
        llm_status = "ok"
    elif ok_count == 0:
        llm_status = "fallback"
    else:
        llm_status = "partial"

    return {
        # 聚合后兼容字段
        "style_score": style_score,
        "special_penalty": special_penalty,

        # 分维度字段（Stage2新增）
        "teaching_style_score": teaching_style_score,
        "major_match_score": major_match_score,

        # 元信息
        "llm_status": llm_status,
        "llm_model": getattr(client.config, "model", ""),
        "prompt_version_style": PROMPT_VERSION_STYLE,
        "prompt_version_major": PROMPT_VERSION_MAJOR,
        "prompt_version_special": PROMPT_VERSION_SPECIAL,

        # reason
        "llm_reason_style": rs_style.reason,
        "llm_reason_major": rs_major.reason,
        "llm_reason_special": rs_special.reason,

        # confidence
        "llm_confidence_style": float(rs_style.confidence),
        "llm_confidence_major": float(rs_major.confidence),
        "llm_confidence_special": float(rs_special.confidence),

        # 调试信息（可选落库）
        "llm_rule_checks_style": rs_style.rule_checks or [],
        "llm_rule_checks_major": rs_major.rule_checks or [],
        "llm_rule_checks_special": rs_special.rule_checks or [],
        "llm_elapsed_style_ms": rs_style.elapsed_ms,
        "llm_elapsed_major_ms": rs_major.elapsed_ms,
        "llm_elapsed_special_ms": rs_special.elapsed_ms,

        # 原始文本（如果你不想存库，可仅接口返回/日志打印）
        "llm_raw_style": rs_style.raw_text,
        "llm_raw_major": rs_major.raw_text,
        "llm_raw_special": rs_special.raw_text,
    }