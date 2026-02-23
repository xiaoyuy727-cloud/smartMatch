# backend/ds_prompt_templates.py
from __future__ import annotations

from typing import Any, Dict

PROMPT_VERSION_STYLE = "style-v1"
PROMPT_VERSION_MAJOR = "major-v1"
PROMPT_VERSION_SPECIAL = "special-v1"


def _safe_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _student_block(s: Dict) -> str:
    return f"""
学生信息：
- 序号: {_safe_text(s.get("seq_no"))}
- 姓名: {_safe_text(s.get("name"))}
- 性别: {_safe_text(s.get("gender"))}
- 学段/年级代码: {_safe_text(s.get("grade_stage"))}
- 辅导方式需求: {_safe_text(s.get("mode"))}
- 科目偏好/需求（1/2/3）: {_safe_text(s.get("subj1"))}, {_safe_text(s.get("subj2"))}, {_safe_text(s.get("subj3"))}
- 薄弱学科与知识短板: {_safe_text(s.get("weakness_text"))}
- 学习风格: {_safe_text(s.get("learning_style"))}
- 兴趣爱好: {_safe_text(s.get("interests_text"))}
- 性格特点: {_safe_text(s.get("personality_text"))}
- 是否优先: {_safe_text(s.get("is_priority"))}
- 特殊需求: {_safe_text(s.get("special_needs_text"))}
""".strip()


def _volunteer_block(v: Dict) -> str:
    return f"""
志愿者信息：
- 序号: {_safe_text(v.get("seq_no"))}
- 姓名: {_safe_text(v.get("name"))}
- 性别: {_safe_text(v.get("gender"))}
- 院系/专业: {_safe_text(v.get("department_major"))}
- 辅导方式: {_safe_text(v.get("mode"))}
- 匹配类型: {_safe_text(v.get("match_mode"))}
- 对学生性别要求: {_safe_text(v.get("gender_requirement"))}
- 学段偏好（1/2/3）: {_safe_text(v.get("grade1"))}, {_safe_text(v.get("grade2"))}, {_safe_text(v.get("grade3"))}
- 科目偏好（1/2/3）: {_safe_text(v.get("subj1"))}, {_safe_text(v.get("subj2"))}, {_safe_text(v.get("subj3"))}
- 教学风格/个人风格: {_safe_text(v.get("teaching_style_text"))}
- 是否参加过: {_safe_text(v.get("participated_before"))}
""".strip()


def style_match_prompt(student: Dict, volunteer: Dict) -> Dict[str, str]:
    """
    输出 JSON:
    {
      "score": 0~20,
      "confidence": 0~1,
      "reason": "...",
      "rule_checks": ["..."]
    }
    """
    system = """
你是一个严格的教育匹配评分器。你只负责“教学风格/性格匹配”评分，不要考虑专业背景，不要考虑特殊需求，不要重复给其他维度加分。
必须输出 JSON（不要 Markdown，不要解释性前缀）。
""".strip()

    user = f"""
请根据以下规则为“教学风格/性格匹配”打分（满分 20 分）：

【评分范围】
- score: 0 到 20 的数字（可带 1 位小数）
- confidence: 0 到 1
- reason: 不超过120字
- rule_checks: 字符串数组（列出命中的规则）

【只允许考虑】
- 学生学习风格（视觉/听觉/动手等）
- 学生性格特点、兴趣
- 志愿者教学风格、性格描述（耐心/活泼/严肃等）

【禁止考虑】
- 志愿者专业背景（这是另一个维度）
- 学生特殊需求（这是另一个维度）
- 性别、线上线下合法性（这些已在系统过滤）

【输出示例】
{{"score": 14, "confidence": 0.82, "reason": "学生偏内向且需要耐心引导，老师风格耐心细致，节奏较匹配。", "rule_checks": ["性格节奏匹配", "教学风格匹配"]}}

{_student_block(student)}

{_volunteer_block(volunteer)}
""".strip()
    return {"system": system, "user": user}


def major_match_prompt(student: Dict, volunteer: Dict) -> Dict[str, str]:
    """
    输出 JSON:
    {
      "score": 0~20,
      "confidence": 0~1,
      "reason": "...",
      "rule_checks": ["..."]
    }
    """
    system = """
你是一个严格的教育匹配评分器。你只负责“志愿者专业背景与学生学业需求匹配”评分，不要考虑教学风格，不要考虑特殊需求。
必须输出 JSON（不要 Markdown，不要解释性前缀）。
""".strip()

    user = f"""
请根据以下规则为“专业匹配度”打分（满分 20 分）：

【评分范围】
- score: 0 到 20 的数字（可带 1 位小数）
- confidence: 0 到 1
- reason: 不超过120字
- rule_checks: 字符串数组

【只允许考虑】
- 志愿者院系/专业
- 学生薄弱学科、知识短板、学科需求（含科目偏好）

【禁止考虑】
- 学生/老师性格与教学风格
- 学生特殊需求
- 性别、线上线下合法性

【输出示例】
{{"score": 16, "confidence": 0.75, "reason": "老师专业背景与学生主要薄弱学科相关，能提供较强学科支持。", "rule_checks": ["专业相关性较高"]}}

{_student_block(student)}

{_volunteer_block(volunteer)}
""".strip()
    return {"system": system, "user": user}


def special_needs_prompt(student: Dict, volunteer: Dict) -> Dict[str, str]:
    """
    输出 JSON:
    {
      "penalty": -20~0,
      "confidence": 0~1,
      "reason": "...",
      "rule_checks": ["..."]
    }
    """
    system = """
你是一个严格的教育匹配评分器。你只负责“特殊需求匹配惩罚”评估。
必须输出 JSON（不要 Markdown，不要解释性前缀）。
""".strip()

    user = f"""
请根据以下规则评估“特殊需求惩罚”（范围 -20 到 0）：

【规则】
- 如果学生没有特殊需求（空白/无/无特殊需求），penalty = 0
- 若特殊需求部分不满足，给负分（如 -3~-12）
- 若明显不满足关键需求，给更大负分（如 -13~-20）
- 若完全满足或未见明显冲突，penalty = 0

【只允许考虑】
- 学生特殊需求文本
- 志愿者已知能力/方式/风格描述（如线上线下方式、风格说明等）

【禁止考虑】
- 专业匹配度
- 风格匹配度重复加减分
- 系统已过滤的合法性条件（性别要求、mode合法性）

【输出示例】
{{"penalty": -8, "confidence": 0.71, "reason": "学生提到需要稳定线下陪伴，老师信息显示线上为主，存在部分不满足。", "rule_checks": ["特殊需求部分不满足"]}}

{_student_block(student)}

{_volunteer_block(volunteer)}
""".strip()
    return {"system": system, "user": user}