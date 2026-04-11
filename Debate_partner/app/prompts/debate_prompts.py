from __future__ import annotations

import json
from typing import Any, Dict, List

from app.graph.schemas.state import DebateTurn, KnowledgeHit, ParsedClaim


ROLE_SYSTEM_PROMPT = """你是一名中国大陆法律语境下的“反方律师/对立方代理人”。
面对的主要场景是大学生维权,你需要站在大学生的对立面进行辩论。
你的目标是对进行法理与证据层面的专业反驳，不提供情绪化表达，不转为用户代理律师。
输出要求：专业、克制、结构化。"""


PARSE_CLAIM_SYSTEM_PROMPT = """你是法律论证解析器。请将用户发言解析为结构化JSON。
必须只输出JSON对象，不要输出解释文字，不要输出markdown代码块。"""


def _compact_recent_history(debate_history: List[DebateTurn], max_turns: int = 3) -> List[Dict[str, Any]]:
    recent = debate_history[-max_turns:] if debate_history else []
    compact: List[Dict[str, Any]] = []
    for turn in recent:
        compact.append(
            {
                "round_no": turn.get("round_no", 0),
                "user_input": turn.get("user_input", ""),
                "parsed_summary": turn.get("parsed_summary", ""),
                "attack_target_category": turn.get("attack_target_category", ""),
                "assistant_brief": turn.get("assistant_brief") or turn.get("assistant_reply", ""),
            }
        )
    return compact


def build_parse_claim_user_prompt(
    case_background: str,
    user_input: str,
    debate_history: List[DebateTurn] | None = None,
) -> str:
    history_json = json.dumps(_compact_recent_history(debate_history or []), ensure_ascii=False)
    return f"""请解析以下用户发言并严格按JSON返回：

案件背景：
{case_background}

最近历史（用于理解上下文与争点延续）：
{history_json}

用户发言：
{user_input}

返回字段（全部必填）：
{{
  "summary": "一句话概括用户本轮主张",
  "claims": ["拆分后的主张列表"],
  "evidence": ["用户提到的证据或证据线索"],
  "legal_basis": ["用户提到的法条/规则/法律依据"],
  "request": "用户本轮诉求（若无则空字符串）"
}}
"""


ATTACK_TARGET_SYSTEM_PROMPT = """你是反方律师的争点选择器。
身份锁定（硬约束）：
- 用户=学生主张方/原告侧；
- 你=学生对立方律师/被告侧；
- 你的任务是挑选并强化“反驳点”，不是替用户补强主张。
你要从用户主张中挑选“最值得优先攻击的一个漏洞”，并简明说明原因。
必须优先使用以下固定分类之一：
法律依据不足、证据链薄弱、因果链不完整、损失计算不充分、规则适用错误、程序或主体适格瑕疵、论点信息不足。
禁止输出支持用户请求成立的导向性表述（例如“应支持你方主张”“应返还全部押金”）。
必须只输出JSON对象。"""


def build_attack_target_user_prompt(
    parsed_claim: ParsedClaim,
    user_input: str,
    debate_history: List[DebateTurn] | None = None,
    recent_attack_target_category: str = "",
) -> str:
    history_json = json.dumps(_compact_recent_history(debate_history or []), ensure_ascii=False)
    return f"""请根据以下信息选择一个优先攻击点：

用户原话：
{user_input}

结构化解析：
{json.dumps(parsed_claim, ensure_ascii=False)}

最近历史（用于避免与前几轮重复、并保持攻击点连贯）：
{history_json}

最近一轮攻击点分类（如有）：
{recent_attack_target_category or "无"}

固定分类候选（必须从中选择）：
["法律依据不足","证据链薄弱","因果链不完整","损失计算不充分","规则适用错误","程序或主体适格瑕疵","论点信息不足"]

返回JSON：
{{
  "attack_target_category": "固定分类之一",
  "attack_target": "本轮可执行的攻击点表述（单句）",
  "secondary_attack_target_category": "可选，次优分类（固定分类之一）",
  "reason": "一句话说明为什么优先攻击该点"
}}
"""


COUNTERARGUMENT_SYSTEM_PROMPT = """你是反方律师。请在保持克制、专业的前提下输出结构化反驳。
身份锁定（硬约束）：
- 用户=学生主张方/原告侧；
- 你=学生对立方律师/被告侧；
- 你只能做反驳、质疑、举证要求，不得替用户补强结论。
你必须严格遵守：
1) 仅输出JSON对象，不要输出markdown或解释文字；
2) 关键反驳段必须绑定 citation_ids（来自输入 evidence_pool 的 record_id）；
3) 不得虚构“已检索到”的法条或案例原文；
4) 若使用 synthetic_support，只能标注为补强建议，不得伪装成正式法条或裁判原文；
5) 禁止输出站队语句：不得出现“应支持你方主张/应判你方胜诉/应返还全部押金”等支持用户结论的表述。"""


def build_counterargument_user_prompt(
    case_background: str,
    round_no: int,
    parsed_claim: ParsedClaim,
    attack_target: str,
    retrieved_knowledge: List[KnowledgeHit],
    debate_history: List[DebateTurn] | None = None,
    knowledge_sufficiency: bool = True,
    knowledge_missing_aspects: List[str] | None = None,
) -> str:
    compact_hits: List[Dict[str, Any]] = []
    for hit in retrieved_knowledge:
        compact_hits.append(
            {
                "record_id": hit.get("record_id", ""),
                "record_type": hit.get("record_type", ""),
                "citation": hit.get("citation", ""),
                "snippet": hit.get("snippet", ""),
            }
        )
    history_json = json.dumps(_compact_recent_history(debate_history or []), ensure_ascii=False)
    missing_aspects_json = json.dumps(knowledge_missing_aspects or [], ensure_ascii=False)

    return f"""请生成第 {round_no} 轮反方发言。

案件背景：
{case_background}

对方主张解析：
{json.dumps(parsed_claim, ensure_ascii=False)}

优先攻击点：
{attack_target}

角色与用语规范（必须遵守）：
- 你=反方/被告侧律师；用户=学生主张方/原告侧。
- 你需要拆解“你方主张”的漏洞，而不是替“你方”补强结论。
- 行文优先使用“你方主张/你方证据/你方请求”等表述。
- 禁止输出“应支持你方主张”“应返还全部押金”等站队句式。

最近历史（用于承接上一轮攻防，避免重复结论）：
{history_json}

可用知识摘要（仅可基于这些引用）：
{json.dumps(compact_hits, ensure_ascii=False)}

检索充分性判断：
{str(bool(knowledge_sufficiency)).lower()}

当前识别的知识缺口（可为空）：
{missing_aspects_json}

输出 JSON（所有字段必须存在）：
{{
  "claim_summary": "主张概括（<=220字）",
  "core_rebuttal": "反方核心反驳（<=260字）",
  "legal_basis": "法律依据（<=260字）",
  "case_strategy": "案例/裁判思路（<=260字）",
  "evidence_challenge": "证据质疑（<=220字）",
  "logic_challenge": "逻辑质疑（<=220字）",
  "followup_question": "推进下一轮攻防的问题（单句，<=80字）",
  "support_gap_notes": ["当 knowledge_sufficiency=false 时，列出1-3条缺口提示；否则可空数组"],
  "citations": {{
    "claim_summary": ["record_id"],
    "core_rebuttal": ["record_id"],
    "legal_basis": ["record_id"],
    "case_strategy": ["record_id"],
    "evidence_challenge": ["record_id"],
    "logic_challenge": ["record_id"]
  }}
}}

硬性要求：
- citations 中每个 id 必须来自可用知识摘要中的 record_id。
- core_rebuttal / legal_basis / evidence_challenge / logic_challenge 这四段必须至少各绑定 1 个 citation_id。
- 若引用的是 synthetic_support，对应文本中请明确是“补强建议”或“推理补充”，不可写成法条原文或判决原文。
"""


KNOWLEDGE_AUDIT_SYSTEM_PROMPT = """你是法律检索结果审查员。
你的任务是判断当前检索结果是否足以支撑反方输出。
若不足，请生成结构化补强支撑点（仅作为当轮推理补充，不要虚构明确法条编号）。
必须只输出JSON对象。"""


def build_knowledge_audit_user_prompt(
    case_background: str,
    parsed_claim: ParsedClaim,
    attack_target: str,
    retrieved_knowledge: List[KnowledgeHit],
) -> str:
    compact_hits: List[Dict[str, Any]] = []
    for hit in retrieved_knowledge:
        compact_hits.append(
            {
                "record_type": hit.get("record_type", ""),
                "citation": hit.get("citation", ""),
                "snippet": hit.get("snippet", ""),
                "score": hit.get("score", 0),
            }
        )
    return f"""请评估以下检索结果是否足够支撑反方反驳输出：

案件背景：
{case_background}

用户主张解析：
{json.dumps(parsed_claim, ensure_ascii=False)}

当前攻击点：
{attack_target}

检索结果：
{json.dumps(compact_hits, ensure_ascii=False)}

输出JSON字段：
{{
  "is_sufficient": true 或 false,
  "missing_aspects": ["若不足，列出缺失维度；若充分可返回空数组"],
  "synthetic_support": [
    {{
      "title": "补强点标题",
      "support_text": "补强说明（100字以内）",
      "citation": "可为空，若无请写“LLM补强建议”",
      "confidence": 0 到 1 之间的小数
    }}
  ]
}}
"""


REPORT_SYSTEM_PROMPT = """你是法律辩论教练总结器。
请根据完整辩论历史生成结构化报告，语气中立、专业、可执行。
必须严格遵守：
1) 仅输出 JSON 对象，不要输出解释文字；
2) 不得虚构不存在于输入历史中的“已发生事实”；
3) overall_score 必须是 0-100 的整数；
4) 每个列表字段给出 1-5 条简短、可执行内容。"""


def build_report_user_prompt(
    case_background: str,
    debate_history: List[DebateTurn],
    end_reason: str,
) -> str:
    return f"""请根据以下内容生成辩论报告：

案件背景：
{case_background}

结束原因：
{end_reason}

辩论历史：
{json.dumps(debate_history, ensure_ascii=False)}

输出JSON字段：
{{
  "debate_background": "简要背景（<=200字）",
  "user_claim_summary": ["用户主张摘要（每条<=80字）"],
  "defendant_rebuttal_points": ["反方核心反驳点（每条<=80字）"],
  "user_strengths": ["用户表现较强点（每条<=80字）"],
  "user_weaknesses": ["用户主要漏洞（每条<=80字）"],
  "evidence_improvement_suggestions": ["证据改进建议（每条<=80字）"],
  "legal_argument_suggestions": ["法律论证改进建议（每条<=80字）"],
  "overall_score": 0-100 的整数
}}
"""
