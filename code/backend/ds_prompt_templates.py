from __future__ import annotations

from typing import Any, Dict, List


def _json_output_requirement() -> str:
    # 强制 JSON 输出，便于解析；reason_raw 允许更长
    return (
        "你必须只输出一个JSON对象，不要输出任何多余文本、不要使用markdown代码块。"
        "JSON字段必须严格包含："
        "score（数字，允许小数）、reason_summary（字符串，<=120字）、reason_raw（字符串，可较长）。"
    )


def build_subjective_messages(
    student_profile: str,
    learning_style: str,
    interests: str,
    student_personality: str,
    teacher_department: str,
    teacher_joined_before: bool,
    teacher_personality: str,
) -> List[Dict[str, Any]]:
    """
    主观匹配度（40分）评分：综合学生主观描述 + 老师主观描述与专业背景
    输出 score: 0~40
    """
    system = (
        "你是一个严格的匹配评分器。"
        "你的任务是根据给定信息，评估老师与学生在主观层面的匹配程度。"
        "评分范围 0~40 分，越高表示越匹配。"
        "请尽量客观、可解释，理由要具体到信息点。"
        + _json_output_requirement()
    )

    rubric = (
        "评分参考（总分40）：\n"
        "1) 学习风格适配（0~15）：老师性格/经验是否适合学生学习风格与学习情况。\n"
        "2) 性格与沟通风格匹配（0~15）：老师性格是否能与学生性格良好互动。\n"
        "3) 兴趣点与激励潜力（0~5）：兴趣爱好是否有助于建立关系/激励学习。\n"
        "4) 专业与背景助益（0~5）：老师院系/经验是否可能更好帮助学生。\n"
        "注意：不要把硬性约束（性别、线上线下）计入此分。"
    )

    user = (
        "【学生信息】\n"
        f"- 学生情况描述：{student_profile}\n"
        f"- 学习风格描述：{learning_style}\n"
        f"- 兴趣爱好：{interests}\n"
        f"- 学生性格：{student_personality}\n\n"
        "【老师信息】\n"
        f"- 院系：{teacher_department}\n"
        f"- 是否参加过过去活动：{1 if teacher_joined_before else 0}\n"
        f"- 个人性格：{teacher_personality}\n\n"
        f"{rubric}\n\n"
        "请输出JSON：{score, reason_summary, reason_raw}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_special_penalty_messages(
    student_special_need: str,
    teacher_all_info_text: str,
) -> List[Dict[str, Any]]:
    """
    特殊需求惩罚（20分）：越不匹配惩罚越高
    输出 score: 0~20（此score表示惩罚分）
    """
    system = (
        "你是一个严格的特殊需求不匹配惩罚评分器。"
        "你的任务是评估老师对学生特殊需求的“不匹配程度”。"
        "输出惩罚分范围 0~20，越高表示越不匹配（惩罚越大）。"
        "如果老师信息明显能满足特殊需求，惩罚应接近0。"
        + _json_output_requirement()
    )

    rubric = (
        "评分参考（惩罚分0~20）：\n"
        "0~3：高度匹配/明显能满足，几乎不惩罚。\n"
        "4~8：基本能满足但有少量风险。\n"
        "9~14：存在明显不确定/不匹配点。\n"
        "15~20：高度不匹配或可能造成明显问题。\n"
        "注意：只根据特殊需求与老师信息评估，不要把科目/学段偏好计入惩罚。"
    )

    user = (
        "【学生特殊需求】\n"
        f"{student_special_need}\n\n"
        "【老师全部信息】\n"
        f"{teacher_all_info_text}\n\n"
        f"{rubric}\n\n"
        "请输出JSON：{score, reason_summary, reason_raw}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]