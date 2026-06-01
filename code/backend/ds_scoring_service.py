from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI
from sqlalchemy.orm import Session

from ds_cache_service import DSCacheService
from ds_prompt_templates import (
    build_special_penalty_messages,
    build_subjective_messages,
)
from matching_rules import has_effective_special_need
from models import Student, Volunteer


@dataclass
class DSScoreResult:
    score_value: float
    reason_summary: str
    reason_raw: str
    status: str  # success / fallback / error / skipped
    error_message: str = ""
    cache_hit: bool = False
    input_hash: str = ""


class DSScoringService:
    """
    DeepSeek 评分服务：
    - 使用 OpenAI SDK + base_url=https://api.deepseek.com
    - 两类评分：
        subjective: 0~40
        special: 0~20 (惩罚分)
    - 失败重试（重试2次，含首次共最多3次尝试）
    - 失败回退：score=0，保留错误信息，任务继续
    - 必须 DB 缓存：pair + score_type + input_hash
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()

        # 重试：按需求“重试2次”
        self.retry_times = 2

        # 初始化客户端（未配置 key 时，调用会明确报错）
        self._client = OpenAI(api_key=self.api_key or "EMPTY_KEY", base_url=self.base_url)

        self._cache = DSCacheService()

    # ------------------------
    # Hash 计算（命中规则：输入文本哈希）
    # ------------------------

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_text(text: Any) -> str:
        if text is None:
            return ""
        return str(text).strip()

    def _subjective_input_hash(self, s: Student, t: Volunteer) -> str:
        payload = "\n".join([
            "SUBJECTIVE_V1",
            f"s.student_profile={self._normalize_text(s.student_profile)}",
            f"s.learning_style={self._normalize_text(s.learning_style)}",
            f"s.interests={self._normalize_text(s.interests)}",
            f"s.personality={self._normalize_text(s.personality)}",
            f"t.department={self._normalize_text(t.department)}",
            f"t.joined_before={1 if t.joined_before else 0}",
            f"t.personality={self._normalize_text(t.personality)}",
        ])
        return self._sha256(payload)

    def _special_input_hash(self, s: Student, t: Volunteer) -> str:
        payload = "\n".join([
            "SPECIAL_V1",
            f"s.special_need={self._normalize_text(s.special_need)}",
            f"t.seq_no={self._normalize_text(t.seq_no)}",
            f"t.name={self._normalize_text(t.name)}",
            f"t.gender={self._normalize_text(t.gender)}",
            f"t.student_no={self._normalize_text(t.student_no)}",
            f"t.email={self._normalize_text(t.email)}",
            f"t.department={self._normalize_text(t.department)}",
            f"t.tutoring_mode={self._normalize_text(t.tutoring_mode)}",
            f"t.match_mode={self._normalize_text(t.match_mode)}",
            f"t.joined_before={1 if t.joined_before else 0}",
            f"t.personality={self._normalize_text(t.personality)}",
            f"t.student_gender_requirement={self._normalize_text(t.student_gender_requirement)}",
            f"t.subj1={t.subj1}",
            f"t.subj2={t.subj2}",
            f"t.subj3={t.subj3}",
            f"t.stage_pref1={t.stage_pref1}",
            f"t.stage_pref2={t.stage_pref2}",
            f"t.stage_pref3={t.stage_pref3}",
            f"t.capacity={t.capacity}",
        ])
        return self._sha256(payload)

    # ------------------------
    # JSON 解析（容错）
    # ------------------------

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        if not text:
            return None
        t = text.strip()

        # 去掉 ```json ``` 包裹
        t = re.sub(r"^```json\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^```\s*", "", t)
        t = re.sub(r"\s*```$", "", t)

        # 直接尝试
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # 截取第一个 { 到最后一个 }
        try:
            start = t.find("{")
            end = t.rfind("}")
            if start >= 0 and end > start:
                sub = t[start:end + 1]
                obj = json.loads(sub)
                if isinstance(obj, dict):
                    return obj
        except Exception:
            return None
        return None

    def _call_ds(self, messages: list[dict[str, Any]]) -> str:
        # 这里不做 stream
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
        )
        return (resp.choices[0].message.content or "").strip()

    # ------------------------
    # 评分：主观匹配度（40）
    # ------------------------

    def score_subjective(self, db: Session, s: Student, t: Volunteer) -> DSScoreResult:
        input_hash = self._subjective_input_hash(s, t)

        cached = self._cache.get_usable(db, s.seq_no, t.seq_no, "subjective", input_hash)
        if cached:
            return DSScoreResult(
                score_value=float(cached.score_value),
                reason_summary=cached.reason_summary or "",
                reason_raw=cached.reason_raw or "",
                status=cached.status,
                error_message=cached.error_message or "",
                cache_hit=True,
                input_hash=input_hash,
            )

        if not self.api_key:
            # 没有配置密钥：直接回退
            msg = "DEEPSEEK_API_KEY 未配置，主观分回退为0"
            return self._finalize_and_cache(
                db=db, s=s, t=t, score_type="subjective", input_hash=input_hash,
                score_value=0.0, reason_summary=msg, reason_raw=msg,
                status="fallback", error_message=msg
            )

        messages = build_subjective_messages(
            student_profile=s.student_profile,
            learning_style=s.learning_style,
            interests=s.interests,
            student_personality=s.personality,
            teacher_department=t.department,
            teacher_joined_before=bool(t.joined_before),
            teacher_personality=t.personality,
        )

        last_error = ""
        raw_text = ""
        for attempt in range(self.retry_times + 1):  # 首次 + 重试2次
            try:
                raw_text = self._call_ds(messages)
                obj = self._extract_json(raw_text)
                if not obj:
                    raise ValueError("DS返回不是有效JSON")
                score = float(obj.get("score", 0.0))
                # clamp
                if score < 0:
                    score = 0.0
                if score > 40:
                    score = 40.0
                reason_summary = str(obj.get("reason_summary", "")).strip()
                reason_raw = str(obj.get("reason_raw", raw_text)).strip()
                return self._finalize_and_cache(
                    db=db, s=s, t=t, score_type="subjective", input_hash=input_hash,
                    score_value=round(score, 2),
                    reason_summary=reason_summary,
                    reason_raw=reason_raw,
                    status="success",
                    error_message=""
                )
            except Exception as e:
                last_error = f"attempt={attempt+1} error={e}"
                continue

        # 全部失败回退
        fallback_summary = "DS主观评分失败，回退为0"
        fallback_raw = (raw_text or "") + ("\n" + last_error if last_error else "")
        return self._finalize_and_cache(
            db=db, s=s, t=t, score_type="subjective", input_hash=input_hash,
            score_value=0.0,
            reason_summary=fallback_summary,
            reason_raw=fallback_raw,
            status="fallback",
            error_message=last_error or fallback_summary
        )

    # ------------------------
    # 评分：特殊需求惩罚（20）
    # ------------------------

    def _teacher_all_info_text(self, t: Volunteer) -> str:
        return "\n".join([
            f"序号：{t.seq_no}",
            f"姓名：{t.name}",
            f"性别：{t.gender}",
            f"学号：{t.student_no}",
            f"学邮：{t.email}",
            f"院系：{t.department}",
            f"辅导方式：{t.tutoring_mode}",
            f"匹配模式：{t.match_mode}",
            f"是否参加过过去的活动：{1 if t.joined_before else 0}",
            f"个人性格：{t.personality}",
            f"对学生性别要求：{t.student_gender_requirement}",
            f"偏好科目1/2/3：{t.subj1},{t.subj2},{t.subj3}",
            f"偏好学段1/2/3：{t.stage_pref1},{t.stage_pref2},{t.stage_pref3}",
            f"可带学生数：{t.capacity}",
        ])

    def score_special_penalty(self, db: Session, s: Student, t: Volunteer) -> DSScoreResult:
        # 无特殊需求：不调用DS，惩罚=0
        if not has_effective_special_need(s.special_need):
            msg = "无特殊需求，惩罚分置0"
            input_hash = self._sha256("SPECIAL_SKIPPED_V1")
            # 可选择写缓存或不写，这里写“skipped”便于统一逻辑
            cached = self._cache.get_usable(db, s.seq_no, t.seq_no, "special", input_hash)
            if cached:
                return DSScoreResult(
                    score_value=float(cached.score_value),
                    reason_summary=cached.reason_summary or msg,
                    reason_raw=cached.reason_raw or msg,
                    status=cached.status,
                    cache_hit=True,
                    input_hash=input_hash,
                )
            return self._finalize_and_cache(
                db=db, s=s, t=t, score_type="special", input_hash=input_hash,
                score_value=0.0,
                reason_summary=msg,
                reason_raw=msg,
                status="skipped",
                error_message=""
            )

        input_hash = self._special_input_hash(s, t)

        cached = self._cache.get_usable(db, s.seq_no, t.seq_no, "special", input_hash)
        if cached:
            return DSScoreResult(
                score_value=float(cached.score_value),
                reason_summary=cached.reason_summary or "",
                reason_raw=cached.reason_raw or "",
                status=cached.status,
                error_message=cached.error_message or "",
                cache_hit=True,
                input_hash=input_hash,
            )

        if not self.api_key:
            msg = "DEEPSEEK_API_KEY 未配置，特殊需求惩罚回退为0"
            return self._finalize_and_cache(
                db=db, s=s, t=t, score_type="special", input_hash=input_hash,
                score_value=0.0, reason_summary=msg, reason_raw=msg,
                status="fallback", error_message=msg
            )

        teacher_all_text = self._teacher_all_info_text(t)
        messages = build_special_penalty_messages(
            student_special_need=s.special_need,
            teacher_all_info_text=teacher_all_text,
        )

        last_error = ""
        raw_text = ""
        for attempt in range(self.retry_times + 1):
            try:
                raw_text = self._call_ds(messages)
                obj = self._extract_json(raw_text)
                if not obj:
                    raise ValueError("DS返回不是有效JSON")
                score = float(obj.get("score", 0.0))
                # clamp
                if score < 0:
                    score = 0.0
                if score > 20:
                    score = 20.0
                reason_summary = str(obj.get("reason_summary", "")).strip()
                reason_raw = str(obj.get("reason_raw", raw_text)).strip()
                return self._finalize_and_cache(
                    db=db, s=s, t=t, score_type="special", input_hash=input_hash,
                    score_value=round(score, 2),
                    reason_summary=reason_summary,
                    reason_raw=reason_raw,
                    status="success",
                    error_message=""
                )
            except Exception as e:
                last_error = f"attempt={attempt+1} error={e}"
                continue

        fallback_summary = "DS特殊需求惩罚评分失败，回退为0"
        fallback_raw = (raw_text or "") + ("\n" + last_error if last_error else "")
        return self._finalize_and_cache(
            db=db, s=s, t=t, score_type="special", input_hash=input_hash,
            score_value=0.0,
            reason_summary=fallback_summary,
            reason_raw=fallback_raw,
            status="fallback",
            error_message=last_error or fallback_summary
        )

    # ------------------------
    # 缓存落库（统一）
    # ------------------------

    def _finalize_and_cache(
        self,
        db: Session,
        s: Student,
        t: Volunteer,
        score_type: str,
        input_hash: str,
        score_value: float,
        reason_summary: str,
        reason_raw: str,
        status: str,
        error_message: str = "",
    ) -> DSScoreResult:
        obj = self._cache.upsert(
            db=db,
            student_seq=s.seq_no,
            teacher_seq=t.seq_no,
            score_type=score_type,
            input_hash=input_hash,
            score_value=float(score_value),
            reason_summary=reason_summary or "",
            reason_raw=reason_raw or "",
            status=status,
            error_message=error_message or "",
        )
        return DSScoreResult(
            score_value=float(obj.score_value),
            reason_summary=obj.reason_summary or "",
            reason_raw=obj.reason_raw or "",
            status=obj.status,
            error_message=obj.error_message or "",
            cache_hit=False,
            input_hash=input_hash,
        )