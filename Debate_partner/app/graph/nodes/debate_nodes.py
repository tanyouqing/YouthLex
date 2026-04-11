from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.graph.schemas.state import (
    AttackTargetCategory,
    DebateReport,
    DebateState,
    DebateTurn,
    KnowledgeHit,
    ParsedClaim,
)
from app.knowledge.repository import search_knowledge
from app.prompts.debate_prompts import (
    ATTACK_TARGET_SYSTEM_PROMPT,
    COUNTERARGUMENT_SYSTEM_PROMPT,
    KNOWLEDGE_AUDIT_SYSTEM_PROMPT,
    PARSE_CLAIM_SYSTEM_PROMPT,
    REPORT_SYSTEM_PROMPT,
    build_attack_target_user_prompt,
    build_counterargument_user_prompt,
    build_knowledge_audit_user_prompt,
    build_parse_claim_user_prompt,
    build_report_user_prompt,
)
from app.services.llm_client import MiniMaxLLMClient


END_KEYWORDS = ("结束", "停止", "到这里", "不用继续")
SECTION_HEADER_PATTERN = re.compile(r"【([^】]+)】")
WHITESPACE_PATTERN = re.compile(r"\s+")
MAX_INPUT_LENGTH = 4000
MIN_MAX_ROUNDS = 1
MAX_MAX_ROUNDS = 20
RETRIEVAL_TOP_K = 6
MAX_SYNTHETIC_SUPPORT = 2
ATTACK_TARGET_CATEGORIES: List[AttackTargetCategory] = [
    "法律依据不足",
    "证据链薄弱",
    "因果链不完整",
    "损失计算不充分",
    "规则适用错误",
    "程序或主体适格瑕疵",
    "论点信息不足",
]
ATTACK_CATEGORY_ALIASES: Dict[str, AttackTargetCategory] = {
    "法律依据不足": "法律依据不足",
    "法条不足": "法律依据不足",
    "法律适用不足": "法律依据不足",
    "证据链薄弱": "证据链薄弱",
    "证据不足": "证据链薄弱",
    "证据不充分": "证据链薄弱",
    "因果链不完整": "因果链不完整",
    "因果关系不足": "因果链不完整",
    "因果关系不清": "因果链不完整",
    "损失计算不充分": "损失计算不充分",
    "损失计算不足": "损失计算不充分",
    "赔偿计算不充分": "损失计算不充分",
    "规则适用错误": "规则适用错误",
    "规则映射不充分": "规则适用错误",
    "规则路径错误": "规则适用错误",
    "程序或主体适格瑕疵": "程序或主体适格瑕疵",
    "程序瑕疵": "程序或主体适格瑕疵",
    "主体适格瑕疵": "程序或主体适格瑕疵",
    "论点信息不足": "论点信息不足",
    "信息不足": "论点信息不足",
    "主张不完整": "论点信息不足",
}
ATTACK_KEYWORDS: Dict[AttackTargetCategory, Tuple[str, ...]] = {
    "法律依据不足": ("法条", "法律", "法规", "依据", "适用法"),
    "证据链薄弱": ("证据", "证明", "凭证", "记录", "材料"),
    "因果链不完整": ("因果", "导致", "造成", "关联", "联系"),
    "损失计算不充分": ("损失", "金额", "赔偿", "计算", "数额"),
    "规则适用错误": ("规则", "条款", "适用", "路径", "逻辑"),
    "程序或主体适格瑕疵": ("程序", "主体", "资格", "适格", "管辖"),
    "论点信息不足": ("不清", "不完整", "缺失", "模糊", "信息"),
}
COUNTERARGUMENT_SEGMENT_KEYS: Tuple[str, ...] = (
    "claim_summary",
    "core_rebuttal",
    "legal_basis",
    "case_strategy",
    "evidence_challenge",
    "logic_challenge",
)
COUNTERARGUMENT_SEGMENT_TITLES: Dict[str, str] = {
    "claim_summary": "主张概括",
    "core_rebuttal": "反方核心反驳",
    "legal_basis": "法律依据",
    "case_strategy": "案例/裁判思路",
    "evidence_challenge": "证据质疑",
    "logic_challenge": "逻辑质疑",
}
COUNTERARGUMENT_SEGMENT_MAXLEN: Dict[str, int] = {
    "claim_summary": 220,
    "core_rebuttal": 260,
    "legal_basis": 260,
    "case_strategy": 260,
    "evidence_challenge": 220,
    "logic_challenge": 220,
}
CRITICAL_CITATION_SEGMENTS: Tuple[str, ...] = (
    "core_rebuttal",
    "legal_basis",
    "evidence_challenge",
    "logic_challenge",
)
DEFAULT_COUNTER_FOLLOWUP = "请你进一步说明关键事实、证据与法律依据之间的一一对应关系。"
LLM_CITATION_PLACEHOLDER_ID = "LLM_SYNTHETIC_PLACEHOLDER"
REPORT_LIST_MAX_ITEMS = 5
REPORT_ITEM_MAX_LEN = 80
REPORT_BG_MAX_LEN = 200
END_REASON_IN_PROGRESS = "IN_PROGRESS"
END_REASON_USER_ENDED = "USER_ENDED"
END_REASON_MAX_ROUNDS = "MAX_ROUNDS_REACHED"
ROLE_DRIFT_STRONG_PHRASES: Tuple[str, ...] = (
    "应支持你方主张",
    "应当支持你方主张",
    "支持你方主张",
    "应支持原告",
    "应当支持原告",
    "支持原告请求",
    "应支持学生主张",
    "应当返还全部押金",
    "应返还全部押金",
    "应判令返还押金",
    "你方请求应予支持",
    "你方主张应予支持",
    "你方应当胜诉",
)
ROLE_DRIFT_SUPPORT_SUBJECTS: Tuple[str, ...] = ("你方", "原告", "学生", "承租人")
ROLE_DRIFT_SUPPORT_VERBS: Tuple[str, ...] = ("支持", "胜诉", "成立", "返还", "退还", "判令")
REBUTTAL_ANCHOR_TERMS: Tuple[str, ...] = (
    "你方",
    "不足",
    "不充分",
    "缺乏",
    "缺少",
    "薄弱",
    "不完整",
    "断裂",
    "跳跃",
    "未能",
    "不能",
    "难以",
    "风险",
    "瑕疵",
    "争议",
    "质疑",
    "举证责任",
    "抗辩",
    "要件",
)
COUNTERARGUMENT_RETRY_SYSTEM_RULE = """角色纠偏补充规则：
- 你仍然是反方/被告侧律师，不得输出支持用户请求成立的任何结论。
- 若你发现自己有“支持你方主张/应返还押金”倾向，必须立刻改写为反驳与举证质疑表达。"""
COUNTERARGUMENT_RETRY_USER_RULE = """【角色纠偏重试要求】
请重新生成，必须保持反方立场。请确保核心段落明确包含“你方主张/你方证据不足/尚未证明”等反驳锚点。"""

_LLM_CLIENT: MiniMaxLLMClient | None = None


def _get_llm_client() -> MiniMaxLLMClient:
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        _LLM_CLIENT = MiniMaxLLMClient()
    return _LLM_CLIENT


def _ensure_list_str(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _normalize_user_text(value: Any) -> str:
    text = str(value or "")
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def _clip_text(value: Any, max_len: int) -> str:
    return str(value or "").strip()[:max_len]


def _normalize_ui_action(value: Any) -> Tuple[str, bool]:
    action = str(value or "send").strip().lower()
    if action in ("send", "end"):
        return action, False
    return "send", True


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _ensure_debug_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _append_debug_warning(debug: Dict[str, Any], warning: str) -> Dict[str, Any]:
    warnings = debug.get("input_warnings")
    if not isinstance(warnings, list):
        warnings = []
    warnings.append(warning)
    debug["input_warnings"] = warnings
    return debug


def _is_new_argument(normalized_text: str, previous_user_inputs: List[str]) -> bool:
    if not normalized_text:
        return False
    previous_normalized = {_normalize_user_text(item) for item in previous_user_inputs}
    previous_normalized.discard("")
    return normalized_text not in previous_normalized


def _safe_parse_claim_fallback(text: str, previous_user_inputs: List[str]) -> ParsedClaim:
    normalized = _normalize_user_text(text)
    claims = [text] if text else []
    return {
        "summary": text[:120],
        "claims": claims,
        "evidence": [],
        "legal_basis": [],
        "request": "",
        "has_new_argument": _is_new_argument(normalized, previous_user_inputs),
        "parse_source": "fallback",
    }


def _empty_parsed_claim() -> ParsedClaim:
    return {
        "summary": "",
        "claims": [],
        "evidence": [],
        "legal_basis": [],
        "request": "",
        "has_new_argument": False,
        "parse_source": "skipped",
    }


def _normalize_attack_target_category(raw_category: Any, attack_text: str = "") -> AttackTargetCategory | None:
    candidate = str(raw_category or "").strip()
    if candidate in ATTACK_TARGET_CATEGORIES:
        return candidate  # type: ignore[return-value]

    if candidate in ATTACK_CATEGORY_ALIASES:
        return ATTACK_CATEGORY_ALIASES[candidate]

    combined = f"{candidate} {str(attack_text or '').strip()}"
    for category, keywords in ATTACK_KEYWORDS.items():
        if any(keyword in combined for keyword in keywords):
            return category

    return None


def _build_attack_target_text(category: AttackTargetCategory, raw_target: Any) -> str:
    target = _clip_text(raw_target, 120)
    if target:
        return target
    return category


def _extract_recent_attack_category(debate_history: Any) -> str:
    if not isinstance(debate_history, list) or not debate_history:
        return ""
    latest = debate_history[-1]
    if not isinstance(latest, dict):
        return ""
    return str(latest.get("attack_target_category", "")).strip()


def _fallback_attack_category(parsed: ParsedClaim, user_text: str) -> AttackTargetCategory:
    claims = parsed.get("claims", [])
    evidence = parsed.get("evidence", [])
    legal_basis = parsed.get("legal_basis", [])

    if not claims:
        return "论点信息不足"
    if not legal_basis:
        return "法律依据不足"
    if not evidence:
        return "证据链薄弱"

    text = str(user_text or "")
    if any(k in text for k in ATTACK_KEYWORDS["损失计算不充分"]):
        return "损失计算不充分"
    if any(k in text for k in ATTACK_KEYWORDS["因果链不完整"]):
        return "因果链不完整"
    if any(k in text for k in ATTACK_KEYWORDS["程序或主体适格瑕疵"]):
        return "程序或主体适格瑕疵"
    return "规则适用错误"


def _pick_reranked_category(
    primary: AttackTargetCategory,
    secondary: AttackTargetCategory | None,
    parsed: ParsedClaim,
    user_text: str,
    recent_category: str,
) -> AttackTargetCategory:
    if secondary and secondary != recent_category:
        return secondary

    fallback_first = _fallback_attack_category(parsed, user_text)
    if fallback_first != recent_category:
        return fallback_first

    for category in ATTACK_TARGET_CATEGORIES:
        if category != recent_category and category != primary:
            return category
    return primary


def _default_attack_reason(category: AttackTargetCategory) -> str:
    reason_map: Dict[AttackTargetCategory, str] = {
        "法律依据不足": "当前主张缺少可直接支撑结论的法律依据映射。",
        "证据链薄弱": "关键事实缺少可核验的证据链闭环支持。",
        "因果链不完整": "事实与责任结论之间的因果链论证尚不完整。",
        "损失计算不充分": "损失项目与金额计算依据未被充分说明。",
        "规则适用错误": "规则适用路径与结论之间存在错配风险。",
        "程序或主体适格瑕疵": "程序条件或主体资格论证存在明显缺口。",
        "论点信息不足": "本轮主张信息密度不足，暂无法形成强论证。",
    }
    return reason_map[category]


def _default_attack_target_text(category: AttackTargetCategory) -> str:
    mapping: Dict[AttackTargetCategory, str] = {
        "法律依据不足": "你方主张的法律依据映射不足，尚未完成要件对应。",
        "证据链薄弱": "你方关键事实的证据链不完整，证明力仍显不足。",
        "因果链不完整": "你方尚未证明事实与责任结论之间的完整因果链。",
        "损失计算不充分": "你方损失项目与金额计算依据尚不充分。",
        "规则适用错误": "你方规则适用路径与结论之间存在错配风险。",
        "程序或主体适格瑕疵": "你方在程序条件或主体适格上仍有待补强。",
        "论点信息不足": "你方当前论点信息不足，难以形成稳定结论。",
    }
    return mapping[category]


def _contains_user_support_signal(text: str) -> bool:
    compact = _normalize_user_text(text).replace(" ", "")
    if not compact:
        return False

    if any(phrase in compact for phrase in ROLE_DRIFT_STRONG_PHRASES):
        return True

    if any(
        f"支持{subject}" in compact and f"不支持{subject}" not in compact
        for subject in ROLE_DRIFT_SUPPORT_SUBJECTS
    ):
        return True

    for subject in ROLE_DRIFT_SUPPORT_SUBJECTS:
        if subject not in compact:
            continue
        for verb in ROLE_DRIFT_SUPPORT_VERBS:
            positive_patterns = (
                f"{subject}应{verb}",
                f"{subject}应当{verb}",
                f"{subject}可以{verb}",
                f"{subject}{verb}",
            )
            if not any(pattern in compact for pattern in positive_patterns):
                continue
            negative_patterns = (
                f"{subject}不应{verb}",
                f"{subject}不能{verb}",
                f"{subject}难以{verb}",
                f"不支持{subject}",
            )
            if any(pattern in compact for pattern in negative_patterns):
                continue
            if "不足" in compact or "不充分" in compact or "未能" in compact:
                continue
            return True
    return False


def _sanitize_attack_target_text(category: AttackTargetCategory, raw_target: Any) -> Tuple[str, bool]:
    target = _build_attack_target_text(category, raw_target)
    if _contains_user_support_signal(target):
        return _default_attack_target_text(category), True
    return target, False


def _detect_counterargument_role_drift(structured: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    segment_texts: Dict[str, str] = {}
    for key in COUNTERARGUMENT_SEGMENT_KEYS:
        segment_texts[key] = _clip_text(structured.get(key, ""), COUNTERARGUMENT_SEGMENT_MAXLEN[key])
    combined = "\n".join(segment_texts.values())

    if _contains_user_support_signal(combined):
        reasons.append("detected_user_support_signal")

    missing_anchor_segments: List[str] = []
    for key in CRITICAL_CITATION_SEGMENTS:
        text = segment_texts.get(key, "")
        if not text:
            continue
        if not any(anchor in text for anchor in REBUTTAL_ANCHOR_TERMS):
            missing_anchor_segments.append(key)

    if "core_rebuttal" in missing_anchor_segments or len(missing_anchor_segments) >= 2:
        reasons.append(f"missing_rebuttal_anchor:{','.join(missing_anchor_segments)}")

    return bool(reasons), reasons


def _parse_labeled_sections(text: str) -> Dict[str, str]:
    content = (text or "").strip()
    if not content:
        return {}

    matches = list(SECTION_HEADER_PATTERN.finditer(content))
    if not matches:
        return {}

    sections: Dict[str, str] = {}
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if title and body and title not in sections:
            sections[title] = body
    return sections


def _extract_core_rebuttal(sections: Dict[str, str], fallback_text: str) -> str:
    for key in ("反方核心反驳", "核心反驳"):
        value = sections.get(key, "").strip()
        if value:
            return value

    for key, value in sections.items():
        if "核心反驳" in key or "反驳" in key:
            value = value.strip()
            if value:
                return value

    if sections:
        first_value = next(iter(sections.values()), "").strip()
        if first_value:
            return first_value

    fallback = (fallback_text or "").strip()
    if fallback:
        return fallback
    return "当前回合未提取到可展示的反驳内容。"


def _build_reply_views(counterargument_draft: str, followup_question: str) -> Dict[str, str]:
    draft = (counterargument_draft or "").strip()
    sections = _parse_labeled_sections(draft)

    draft_followup = sections.get("进一步追问", "").strip()
    followup = (followup_question or "").strip() or draft_followup
    if not followup:
        followup = "请继续补充你的关键证据。"

    core_rebuttal = _extract_core_rebuttal(sections=sections, fallback_text=draft)

    brief = f"【核心反驳】{core_rebuttal}\n【进一步追问】{followup}"

    if draft:
        detail = draft
        if "【进一步追问】" not in detail:
            detail = f"{detail}\n【进一步追问】{followup}"
    else:
        detail = brief

    return {
        "assistant_brief": brief,
        "assistant_detail": detail,
    }


def _resolve_end_reason(state: DebateState) -> str:
    reason = str(state.get("end_reason", "")).strip()
    if reason:
        return reason

    reason_code = str(state.get("end_reason_code", "")).strip()
    if reason_code == END_REASON_USER_ENDED:
        return "用户点击结束辩论"
    if reason_code == END_REASON_MAX_ROUNDS:
        max_rounds = _clamp(_safe_int(state.get("max_rounds", 5), 5), MIN_MAX_ROUNDS, MAX_MAX_ROUNDS)
        return f"达到预设最大轮次（{max_rounds}）"

    if state.get("ui_action", "send") == "end":
        return "用户点击结束辩论"

    max_rounds = state.get("max_rounds", 5)
    round_index = state.get("round_index", 0)
    if round_index >= max_rounds:
        return f"达到预设最大轮次（{max_rounds}）"

    return "流程结束"


def _build_report_notice(end_reason: str, degraded: bool) -> Tuple[str, str]:
    brief = (
        "【核心反驳】本轮不再追加新的攻防观点，辩论已结束。\n"
        "【进一步追问】请查看页面右侧的“辩论总结报告”区域。"
    )
    mode = "降级模式" if degraded else "标准模式"
    detail = f"{brief}\n【系统说明】结束原因：{end_reason}；报告生成方式：{mode}。"
    return brief, detail


def init_session(state: DebateState) -> DebateState:
    max_rounds = _clamp(_safe_int(state.get("max_rounds", 5), 5), MIN_MAX_ROUNDS, MAX_MAX_ROUNDS)
    round_index = max(0, _safe_int(state.get("round_index", 0), 0))
    ui_action, action_defaulted = _normalize_ui_action(state.get("ui_action", "send"))

    debate_history = state.get("debate_history", [])
    if not isinstance(debate_history, list):
        debate_history = []
    previous_user_inputs = state.get("previous_user_inputs", [])
    if not isinstance(previous_user_inputs, list):
        previous_user_inputs = []

    debug = _ensure_debug_dict(state.get("debug", {}))
    if action_defaulted:
        _append_debug_warning(debug, "init_session: ui_action 非法，已回退为 send。")

    report = state.get("report", {})
    if not isinstance(report, dict):
        report = {}
    report_source = str(state.get("report_source", "")).strip()
    if report_source not in ("llm", "fallback"):
        report_source = ""

    return {
        "max_rounds": max_rounds,
        "round_index": round_index,
        "debate_history": list(debate_history),
        "previous_user_inputs": list(previous_user_inputs),
        "no_new_argument_streak": max(0, _safe_int(state.get("no_new_argument_streak", 0), 0)),
        "should_end": False,
        "end_reason": state.get("end_reason", ""),
        "end_reason_code": state.get("end_reason_code", END_REASON_IN_PROGRESS),
        "ui_action": ui_action,
        "report": dict(report),
        "report_source": report_source,
        "report_quality_flags": list(state.get("report_quality_flags", []))
        if isinstance(state.get("report_quality_flags", []), list)
        else [],
        "parsed_claim": {},
        "attack_target": "",
        "attack_target_category": "论点信息不足",
        "attack_target_reason": "",
        "attack_target_source": "fallback",
        "retrieved_knowledge": [],
        "retrieval_mode": "keyword_fallback",
        "knowledge_sufficiency": True,
        "knowledge_missing_aspects": [],
        "counterargument_structured": {},
        "counterargument_citations": {},
        "counterargument_quality_flags": [],
        "counterargument_draft": "",
        "followup_question": "",
        "input_valid": True,
        "input_error_code": "",
        "input_error_message": "",
        "normalized_user_input": "",
        "debug": debug,
    }


def fetch_user_input(state: DebateState) -> DebateState:
    raw_input = str(state.get("current_user_input", ""))
    current = raw_input.strip()
    normalized = _normalize_user_text(raw_input)
    ui_action, action_defaulted = _normalize_ui_action(state.get("ui_action", "send"))

    input_valid = True
    input_error_code = ""
    input_error_message = ""

    if ui_action == "send" and not normalized:
        input_valid = False
        input_error_code = "INVALID_ARGUMENT"
        input_error_message = "发送内容不能为空，请输入你的主张后再发送。"
    elif len(current) > MAX_INPUT_LENGTH:
        input_valid = False
        input_error_code = "INVALID_ARGUMENT"
        input_error_message = f"输入内容过长，请控制在 {MAX_INPUT_LENGTH} 字以内。"

    debug = _ensure_debug_dict(state.get("debug", {}))
    if action_defaulted:
        _append_debug_warning(debug, "fetch_user_input: ui_action 非法，已回退为 send。")

    return {
        "current_user_input": current,
        "normalized_user_input": normalized,
        "ui_action": ui_action,
        "input_valid": input_valid,
        "input_error_code": input_error_code,
        "input_error_message": input_error_message,
        "debug": debug,
    }


def handle_invalid_input(state: DebateState) -> DebateState:
    error_code = str(state.get("input_error_code", "")).strip() or "INVALID_ARGUMENT"
    error_message = str(state.get("input_error_message", "")).strip() or "输入不合法，请检查后重试。"
    brief = f"【输入校验】{error_message}\n【操作建议】请修改输入后重新发送。"
    detail = f"{brief}\n【错误码】{error_code}"

    return {
        "assistant_reply": brief,
        "assistant_brief": brief,
        "assistant_detail": detail,
        "should_end": False,
    }


def parse_user_claim(state: DebateState) -> DebateState:
    text = str(state.get("current_user_input", "")).strip()
    normalized_text = _normalize_user_text(state.get("normalized_user_input", text))
    previous = state.get("previous_user_inputs", [])
    if not isinstance(previous, list):
        previous = []

    if not bool(state.get("input_valid", True)) or not normalized_text:
        parsed = _empty_parsed_claim()
        return {"parsed_claim": parsed}

    try:
        llm = _get_llm_client()
        result = llm.chat_json(
            system_prompt=PARSE_CLAIM_SYSTEM_PROMPT,
            user_prompt=build_parse_claim_user_prompt(
                case_background=state.get("case_background", ""),
                user_input=text,
                debate_history=state.get("debate_history", []),
            ),
            temperature=1.0,
        )

        parsed: ParsedClaim = {
            "summary": _clip_text(result.get("summary", text[:120]), 300),
            "claims": [item[:300] for item in _ensure_list_str(result.get("claims"))[:12]],
            "evidence": [item[:300] for item in _ensure_list_str(result.get("evidence"))[:12]],
            "legal_basis": [item[:200] for item in _ensure_list_str(result.get("legal_basis"))[:12]],
            "request": _clip_text(result.get("request", ""), 500),
            "has_new_argument": _is_new_argument(normalized_text, previous),
            "parse_source": "llm",
        }
        if not parsed["claims"]:
            parsed["claims"] = [_clip_text(text, 300)]
        return {"parsed_claim": parsed}
    except Exception as exc:
        parsed = _safe_parse_claim_fallback(text, previous)
        debug = _ensure_debug_dict(state.get("debug", {}))
        debug["parse"] = {
            "error_code": "PARSE_CLAIM_LLM_FAILED",
            "error_message": str(exc),
            "source": "fallback",
        }
        return {"parsed_claim": parsed, "debug": debug}


def identify_attack_target(state: DebateState) -> DebateState:
    parsed = state.get("parsed_claim", {})
    if not isinstance(parsed, dict):
        parsed = {}
    text = str(state.get("current_user_input", "")).strip()
    debate_history = state.get("debate_history", [])
    recent_category = _extract_recent_attack_category(debate_history)

    debug = _ensure_debug_dict(state.get("debug", {}))
    attack_debug: Dict[str, Any] = {
        "error_code": "",
        "fallback_reason": "",
        "rerank_applied": False,
    }

    if parsed.get("parse_source") == "skipped":
        category: AttackTargetCategory = "论点信息不足"
        attack_debug["fallback_reason"] = "parse_user_claim 为 skipped，攻击点自动降级。"
        debug["attack"] = attack_debug
        return {
            "attack_target": _default_attack_target_text(category),
            "attack_target_category": category,
            "attack_target_reason": _default_attack_reason(category),
            "attack_target_source": "fallback",
            "debug": debug,
        }

    try:
        llm = _get_llm_client()
        result = llm.chat_json(
            system_prompt=ATTACK_TARGET_SYSTEM_PROMPT,
            user_prompt=build_attack_target_user_prompt(
                parsed_claim=parsed,
                user_input=text,
                debate_history=debate_history,
                recent_attack_target_category=recent_category,
            ),
            temperature=0.4,
        )
        raw_target = result.get("attack_target", "")
        primary = _normalize_attack_target_category(
            raw_category=result.get("attack_target_category", ""),
            attack_text=str(raw_target),
        )
        secondary = _normalize_attack_target_category(
            raw_category=result.get("secondary_attack_target_category", ""),
            attack_text=str(raw_target),
        )
        reason = _clip_text(result.get("reason", ""), 200)
        source = "llm"

        if primary is None:
            primary = _fallback_attack_category(parsed, text)
            source = "fallback"
            attack_debug["error_code"] = "ATTACK_TARGET_INVALID_OUTPUT"
            attack_debug["fallback_reason"] = "LLM 输出未命中固定分类，已回退规则分类。"

        if recent_category and primary == recent_category:
            reranked = _pick_reranked_category(
                primary=primary,
                secondary=secondary,
                parsed=parsed,
                user_text=text,
                recent_category=recent_category,
            )
            if reranked != primary:
                primary = reranked
                source = "reranked"
                attack_debug["rerank_applied"] = True
                if not attack_debug["error_code"]:
                    attack_debug["error_code"] = "ATTACK_TARGET_RERANK_APPLIED"
                if not attack_debug["fallback_reason"]:
                    attack_debug["fallback_reason"] = "与上一轮分类重复，自动切换次优攻击点。"
                raw_target = ""

        target, target_sanitized = _sanitize_attack_target_text(primary, raw_target)
        if target_sanitized:
            source = "fallback"
            if not attack_debug["error_code"]:
                attack_debug["error_code"] = "ATTACK_TARGET_ROLE_DRIFT_SANITIZED"
            if not attack_debug["fallback_reason"]:
                attack_debug["fallback_reason"] = "攻击点文本出现站队倾向，已替换为标准反驳文案。"
        if not reason:
            reason = _default_attack_reason(primary)

        debug["attack"] = attack_debug
        return {
            "attack_target": target,
            "attack_target_category": primary,
            "attack_target_reason": reason,
            "attack_target_source": source,
            "debug": debug,
        }
    except Exception as exc:
        category = _fallback_attack_category(parsed, text)
        attack_debug["error_code"] = "ATTACK_TARGET_LLM_FAILED"
        attack_debug["fallback_reason"] = "LLM 调用异常，已回退规则分类。"
        attack_debug["error_message"] = str(exc)
        debug["attack"] = attack_debug
        return {
            "attack_target": _default_attack_target_text(category),
            "attack_target_category": category,
            "attack_target_reason": _default_attack_reason(category),
            "attack_target_source": "fallback",
            "debug": debug,
        }


def retrieve_knowledge(state: DebateState) -> DebateState:
    history = state.get("debate_history", [])
    recent_summary = ""
    if history:
        recent_summary = str(history[-1].get("parsed_summary", "")).strip()

    query = " ".join(
        [
            state.get("current_user_input", ""),
            state.get("attack_target", ""),
            " ".join(state.get("parsed_claim", {}).get("claims", [])),
            recent_summary,
        ]
    )
    hits, retrieval_debug = search_knowledge(
        query=query,
        scenario_hint=state.get("scenario_hint", ""),
        top_k=RETRIEVAL_TOP_K,
    )

    debug = _ensure_debug_dict(state.get("debug", {}))
    debug["retrieval"] = retrieval_debug
    mode = str(retrieval_debug.get("mode", "keyword_fallback"))
    if mode not in ("vector", "keyword_fallback"):
        mode = "keyword_fallback"
    return {
        "retrieved_knowledge": hits,
        "retrieval_mode": mode,
        "debug": debug,
    }


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_synthetic_hits(
    synthetic_rows: List[Dict[str, Any]],
    base_count: int,
) -> List[KnowledgeHit]:
    hits: List[KnowledgeHit] = []
    for idx, row in enumerate(synthetic_rows[:MAX_SYNTHETIC_SUPPORT]):
        title = _clip_text(row.get("title", ""), 80)
        support_text = _clip_text(row.get("support_text", ""), 160)
        if not title and not support_text:
            continue
        citation = _clip_text(row.get("citation", ""), 120) or "LLM补强建议"
        confidence = _safe_float(row.get("confidence", 0.6), 0.6)
        confidence = max(0.0, min(1.0, confidence))
        snippet = f"{title}：{support_text}" if title else support_text
        hits.append(
            {
                "record_id": f"SYNTHETIC_SUPPORT_{base_count + idx + 1:04d}",
                "record_type": "synthetic_support",
                "score": int(confidence * 100),
                "citation": citation,
                "snippet": snippet,
            }
        )
    return hits


def assess_knowledge_support(state: DebateState) -> DebateState:
    hits = state.get("retrieved_knowledge", [])
    if not isinstance(hits, list):
        hits = []

    debug = _ensure_debug_dict(state.get("debug", {}))
    audit_debug: Dict[str, Any] = {
        "source": "llm",
        "is_sufficient": bool(hits),
        "synthetic_count": 0,
        "error_code": "",
    }

    try:
        llm = _get_llm_client()
        result = llm.chat_json(
            system_prompt=KNOWLEDGE_AUDIT_SYSTEM_PROMPT,
            user_prompt=build_knowledge_audit_user_prompt(
                case_background=state.get("case_background", ""),
                parsed_claim=state.get("parsed_claim", {}),
                attack_target=state.get("attack_target", ""),
                retrieved_knowledge=hits,
            ),
            temperature=0.6,
        )

        is_sufficient = bool(result.get("is_sufficient", bool(hits)))
        missing_aspects = _ensure_list_str(result.get("missing_aspects"))
        synthetic_rows = result.get("synthetic_support")
        if not isinstance(synthetic_rows, list):
            synthetic_rows = []

        synthetic_hits: List[KnowledgeHit] = []
        if not is_sufficient:
            synthetic_hits = _build_synthetic_hits(
                synthetic_rows=[row for row in synthetic_rows if isinstance(row, dict)],
                base_count=len(hits),
            )
            if synthetic_hits:
                hits = list(hits) + synthetic_hits

        audit_debug["is_sufficient"] = is_sufficient
        audit_debug["synthetic_count"] = len(synthetic_hits)
        debug["knowledge_audit"] = audit_debug
        return {
            "retrieved_knowledge": hits[: RETRIEVAL_TOP_K + MAX_SYNTHETIC_SUPPORT],
            "knowledge_sufficiency": is_sufficient,
            "knowledge_missing_aspects": missing_aspects,
            "debug": debug,
        }
    except Exception as exc:
        audit_debug["source"] = "fallback"
        audit_debug["is_sufficient"] = bool(hits)
        audit_debug["error_code"] = "KNOWLEDGE_AUDIT_FAILED"
        audit_debug["error_message"] = str(exc)
        debug["knowledge_audit"] = audit_debug
        return {
            "retrieved_knowledge": hits,
            "knowledge_sufficiency": bool(hits),
            "knowledge_missing_aspects": [],
            "debug": debug,
        }


def _normalize_parsed_claim_for_counter(value: Any) -> ParsedClaim:
    parsed = _ensure_dict(value)
    claims = [_clip_text(item, 300) for item in _ensure_list_str(parsed.get("claims"))[:10]]
    evidence = [_clip_text(item, 300) for item in _ensure_list_str(parsed.get("evidence"))[:10]]
    legal_basis = [_clip_text(item, 220) for item in _ensure_list_str(parsed.get("legal_basis"))[:10]]
    summary = _clip_text(parsed.get("summary", ""), 260)
    request = _clip_text(parsed.get("request", ""), 220)
    if not summary and claims:
        summary = claims[0]
    if not summary:
        summary = "你方主张尚未完整陈述。"
    return {
        "summary": summary,
        "claims": claims,
        "evidence": evidence,
        "legal_basis": legal_basis,
        "request": request,
        "has_new_argument": bool(parsed.get("has_new_argument", True)),
        "parse_source": parsed.get("parse_source", "fallback"),
    }


def _normalize_retrieved_hits(value: Any) -> List[KnowledgeHit]:
    if not isinstance(value, list):
        return []

    normalized: List[KnowledgeHit] = []
    seen_ids: Dict[str, int] = {}
    for idx, raw in enumerate(value[: RETRIEVAL_TOP_K + MAX_SYNTHETIC_SUPPORT]):
        row = _ensure_dict(raw)
        record_id = _clip_text(row.get("record_id", ""), 80) or f"EVIDENCE_{idx + 1:04d}"
        if record_id in seen_ids:
            seen_ids[record_id] += 1
            record_id = f"{record_id}_{seen_ids[record_id]}"
        else:
            seen_ids[record_id] = 1

        record_type = _clip_text(row.get("record_type", ""), 40) or "rebuttal_template"
        score = _clamp(_safe_int(row.get("score", 0), 0), 0, 100)
        citation = _clip_text(row.get("citation", ""), 200)
        snippet = _clip_text(row.get("snippet", ""), 320)
        if not citation and not snippet:
            continue
        normalized.append(
            {
                "record_id": record_id,
                "record_type": record_type,  # type: ignore[typeddict-item]
                "score": score,
                "citation": citation,
                "snippet": snippet,
            }
        )
    return normalized


def _build_evidence_pool(hits: List[KnowledgeHit]) -> List[Dict[str, str]]:
    evidence_pool: List[Dict[str, str]] = []
    for hit in hits:
        record_id = _clip_text(hit.get("record_id", ""), 80)
        if not record_id:
            continue
        record_type = _clip_text(hit.get("record_type", ""), 40) or "rebuttal_template"
        citation = _clip_text(hit.get("citation", ""), 200)
        snippet = _clip_text(hit.get("snippet", ""), 320)
        if not citation:
            citation = "LLM补强建议" if record_type == "synthetic_support" else "未提供引用标题"
        evidence_pool.append(
            {
                "record_id": record_id,
                "record_type": record_type,
                "citation": citation,
                "snippet": snippet,
            }
        )
    return evidence_pool


def _pick_citation_for_segment(segment_key: str, evidence_pool: List[Dict[str, str]]) -> str:
    preferred_types: Dict[str, Tuple[str, ...]] = {
        "legal_basis": ("statute", "issue_rule", "synthetic_support"),
        "case_strategy": ("case", "rebuttal_template", "synthetic_support"),
        "evidence_challenge": ("case", "issue_rule", "synthetic_support"),
    }
    candidates = preferred_types.get(segment_key, ())
    if candidates:
        for item in evidence_pool:
            if item.get("record_type", "") in candidates:
                return item.get("record_id", "")
    if evidence_pool:
        return evidence_pool[0].get("record_id", "")
    return LLM_CITATION_PLACEHOLDER_ID


def _default_segment_text(
    segment_key: str,
    parsed: ParsedClaim,
    attack_target: str,
    evidence_pool: List[Dict[str, str]],
) -> str:
    summary = _clip_text(parsed.get("summary", ""), 220) or "你方主张尚未完整陈述。"
    first_evidence = evidence_pool[0].get("snippet", "") if evidence_pool else ""
    if segment_key == "claim_summary":
        return summary
    if segment_key == "core_rebuttal":
        return f"当前主要漏洞集中在“{attack_target}”，现有材料不足以直接支持你方结论。"
    if segment_key == "legal_basis":
        return "现有法律依据与请求结论之间的要件映射不足，建议补充明确法条适用路径。"
    if segment_key == "case_strategy":
        return "从类案思路看，应先论证责任成立，再论证损失范围与举证责任分配。"
    if segment_key == "evidence_challenge":
        return "你方证据链缺少关键节点，尚不足以完成事实到责任的完整闭环。"
    if segment_key == "logic_challenge":
        detail = f"；可参考当前材料：{first_evidence}" if first_evidence else ""
        return f"当前论证存在结论先行的问题，关键推理环节仍需补足{detail}"
    return summary


def _sanitize_counterargument_output(
    result: Dict[str, Any],
    parsed: ParsedClaim,
    attack_target: str,
    evidence_pool: List[Dict[str, str]],
    knowledge_sufficiency: bool,
    knowledge_missing_aspects: List[str],
) -> Tuple[Dict[str, Any], Dict[str, List[str]], str, List[str], bool]:
    evidence_ids = {item.get("record_id", "") for item in evidence_pool}
    structured: Dict[str, Any] = {}
    citation_map: Dict[str, List[str]] = {}
    quality_flags: List[str] = []
    repair_applied = False

    citation_block = _ensure_dict(result.get("citations", {}))
    for key in COUNTERARGUMENT_SEGMENT_KEYS:
        text = _clip_text(result.get(key, ""), COUNTERARGUMENT_SEGMENT_MAXLEN[key])
        if not text:
            text = _default_segment_text(
                segment_key=key,
                parsed=parsed,
                attack_target=attack_target,
                evidence_pool=evidence_pool,
            )
            repair_applied = True
        structured[key] = text

        raw_ids = [_clip_text(item, 80) for item in _ensure_list_str(citation_block.get(key, []))[:4]]
        valid_ids = [item for item in raw_ids if item and item in evidence_ids]
        if raw_ids and len(valid_ids) != len(raw_ids):
            repair_applied = True
            quality_flags.append("invalid_citation_removed")
        citation_map[key] = list(dict.fromkeys(valid_ids))

    support_gap_notes = [_clip_text(item, 120) for item in _ensure_list_str(result.get("support_gap_notes"))[:3]]
    if not knowledge_sufficiency and not support_gap_notes:
        support_gap_notes = [_clip_text(item, 120) for item in knowledge_missing_aspects[:3]]
        if not support_gap_notes:
            support_gap_notes = ["当前检索支撑不足，建议补充可核验的事实证据与法条适配论证。"]
        repair_applied = True
    structured["support_gap_notes"] = [item for item in support_gap_notes if item]

    followup = _clip_text(result.get("followup_question", ""), 80)
    if not followup:
        followup = DEFAULT_COUNTER_FOLLOWUP
        repair_applied = True

    return structured, citation_map, followup, quality_flags, repair_applied


def _apply_strong_citation(
    citation_map: Dict[str, List[str]],
    evidence_pool: List[Dict[str, str]],
) -> Tuple[Dict[str, List[str]], List[str], bool]:
    missing_segments: List[str] = []
    used_placeholder = False
    for key in CRITICAL_CITATION_SEGMENTS:
        ids = citation_map.get(key, [])
        if ids:
            continue
        pick = _pick_citation_for_segment(key, evidence_pool)
        if not pick:
            pick = LLM_CITATION_PLACEHOLDER_ID
        if pick == LLM_CITATION_PLACEHOLDER_ID:
            used_placeholder = True
        citation_map[key] = [pick]
        missing_segments.append(key)
    return citation_map, missing_segments, used_placeholder


def _compose_counterargument_draft(structured: Dict[str, Any], followup_question: str) -> str:
    lines: List[str] = []
    for key in COUNTERARGUMENT_SEGMENT_KEYS:
        title = COUNTERARGUMENT_SEGMENT_TITLES[key]
        text = _clip_text(structured.get(key, ""), COUNTERARGUMENT_SEGMENT_MAXLEN[key])
        if not text:
            text = "（待补充）"
        lines.append(f"【{title}】{text}")
    gap_notes = [_clip_text(item, 120) for item in _ensure_list_str(structured.get("support_gap_notes"))[:3]]
    if gap_notes:
        lines.append(f"【支撑缺口提示】{'；'.join(gap_notes)}")
    lines.append(f"【进一步追问】{_clip_text(followup_question, 80) or DEFAULT_COUNTER_FOLLOWUP}")
    return "\n".join(lines)


def _fallback_counterargument_payload(
    parsed: ParsedClaim,
    attack_target: str,
    evidence_pool: List[Dict[str, str]],
    knowledge_sufficiency: bool,
    knowledge_missing_aspects: List[str],
) -> Dict[str, Any]:
    summary = _clip_text(parsed.get("summary", ""), 220) or "你方主张尚未完整陈述。"
    law_refs = [item.get("citation", "") for item in evidence_pool if item.get("record_type") in ("statute", "issue_rule")]
    case_refs = [item.get("citation", "") for item in evidence_pool if item.get("record_type") == "case"]
    law_part = "、".join([ref for ref in law_refs if ref][:2]) or "（当前暂无可核验法条引用）"
    case_part = "、".join([ref for ref in case_refs if ref][:2]) or "（当前暂无可核验类案引用）"

    structured: Dict[str, Any] = {
        "claim_summary": summary,
        "core_rebuttal": f"当前主要漏洞在于“{attack_target}”，你方论证尚未形成可核验闭环。",
        "legal_basis": f"现阶段可参考：{law_part}",
        "case_strategy": f"类案思路可参考：{case_part}",
        "evidence_challenge": "现有证据不足以支撑关键事实链条，需补充原始材料与对应关系。",
        "logic_challenge": "目前存在结论先行的问题，尚未完成“事实-规则-结论”的完整推导。",
        "support_gap_notes": [] if knowledge_sufficiency else [_clip_text(item, 120) for item in knowledge_missing_aspects[:3]],
    }
    followup = "请你补充关键事实、证据与法条之间的一一对应关系。"

    citation_map: Dict[str, List[str]] = {key: [] for key in COUNTERARGUMENT_SEGMENT_KEYS}
    if evidence_pool:
        first_id = evidence_pool[0].get("record_id", "")
        if first_id:
            citation_map["claim_summary"] = [first_id]
            citation_map["core_rebuttal"] = [first_id]
            citation_map["evidence_challenge"] = [first_id]
            citation_map["logic_challenge"] = [first_id]
    for key in ("legal_basis", "case_strategy"):
        picked = _pick_citation_for_segment(key, evidence_pool)
        if picked:
            citation_map[key] = [picked]

    citation_map, missing_segments, used_placeholder = _apply_strong_citation(citation_map, evidence_pool)
    quality_flags = ["fallback_used"]
    quality_flags.extend([f"missing_citation:{segment}" for segment in missing_segments])
    if used_placeholder:
        quality_flags.append("llm_placeholder_citation")
        structured["support_gap_notes"] = list(structured.get("support_gap_notes", [])) + ["关键段落引用不足，已注入 LLM 补强占位。"]

    draft = _compose_counterargument_draft(structured, followup)
    return {
        "counterargument_structured": structured,
        "counterargument_citations": citation_map,
        "counterargument_quality_flags": list(dict.fromkeys(quality_flags)),
        "counterargument_draft": draft,
        "followup_question": followup,
        "missing_citation_segments": missing_segments,
    }


def build_counterargument(state: DebateState) -> DebateState:
    parsed = _normalize_parsed_claim_for_counter(state.get("parsed_claim", {}))
    hits = _normalize_retrieved_hits(state.get("retrieved_knowledge", []))
    evidence_pool = _build_evidence_pool(hits)
    attack_target = _clip_text(state.get("attack_target", ""), 120) or "论证链不足"
    knowledge_sufficiency = bool(state.get("knowledge_sufficiency", True))
    knowledge_missing_aspects = [_clip_text(item, 120) for item in _ensure_list_str(state.get("knowledge_missing_aspects"))[:3]]

    debug = _ensure_debug_dict(state.get("debug", {}))
    counter_debug: Dict[str, Any] = {
        "error_code": "",
        "repair_applied": False,
        "missing_citation_segments": [],
        "source_mode": "llm",
        "role_drift_detected": False,
        "retry_applied": False,
    }

    def _return_fallback(error_code: str, error_message: str = "", extra_flags: List[str] | None = None) -> DebateState:
        fallback = _fallback_counterargument_payload(
            parsed=parsed,
            attack_target=attack_target,
            evidence_pool=evidence_pool,
            knowledge_sufficiency=knowledge_sufficiency,
            knowledge_missing_aspects=knowledge_missing_aspects,
        )
        quality_flags = _ensure_list_str(fallback.get("counterargument_quality_flags"))
        if extra_flags:
            quality_flags.extend(extra_flags)
        fallback["counterargument_quality_flags"] = list(dict.fromkeys(quality_flags))

        counter_debug["error_code"] = error_code
        if error_message:
            counter_debug["error_message"] = error_message
        counter_debug["repair_applied"] = True
        counter_debug["source_mode"] = "fallback"
        counter_debug["missing_citation_segments"] = fallback.pop("missing_citation_segments", [])
        debug["counterargument"] = counter_debug
        fallback["debug"] = debug
        return fallback

    try:
        llm = _get_llm_client()
        base_user_prompt = build_counterargument_user_prompt(
            case_background=state.get("case_background", ""),
            round_no=state.get("round_index", 0) + 1,
            parsed_claim=parsed,
            attack_target=attack_target,
            retrieved_knowledge=hits,
            debate_history=state.get("debate_history", []),
            knowledge_sufficiency=knowledge_sufficiency,
            knowledge_missing_aspects=knowledge_missing_aspects,
        )

        def _run_attempt(temperature: float, retry_mode: bool = False) -> Dict[str, Any]:
            system_prompt = COUNTERARGUMENT_SYSTEM_PROMPT
            user_prompt = base_user_prompt
            if retry_mode:
                system_prompt = f"{system_prompt}\n\n{COUNTERARGUMENT_RETRY_SYSTEM_RULE}"
                user_prompt = f"{user_prompt}\n\n{COUNTERARGUMENT_RETRY_USER_RULE}"

            result = llm.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
            if not isinstance(result, dict):
                raise ValueError("COUNTERARGUMENT_INVALID_OUTPUT")
            if not any(_clip_text(result.get(key, ""), 10) for key in COUNTERARGUMENT_SEGMENT_KEYS):
                raise ValueError("COUNTERARGUMENT_EMPTY_OUTPUT")

            structured, citation_map, followup, quality_flags, repair_applied = _sanitize_counterargument_output(
                result=result,
                parsed=parsed,
                attack_target=attack_target,
                evidence_pool=evidence_pool,
                knowledge_sufficiency=knowledge_sufficiency,
                knowledge_missing_aspects=knowledge_missing_aspects,
            )
            citation_map, missing_segments, used_placeholder = _apply_strong_citation(citation_map, evidence_pool)
            if missing_segments:
                repair_applied = True
                quality_flags.extend([f"missing_citation:{segment}" for segment in missing_segments])
            if used_placeholder:
                quality_flags.append("llm_placeholder_citation")
                notes = _ensure_list_str(structured.get("support_gap_notes"))
                notes.append("关键段落引用不足，已注入 LLM 补强占位。")
                structured["support_gap_notes"] = list(dict.fromkeys(notes))

            role_drift_detected, role_drift_reasons = _detect_counterargument_role_drift(structured)
            return {
                "structured": structured,
                "citation_map": citation_map,
                "followup": followup,
                "quality_flags": list(dict.fromkeys(quality_flags)),
                "repair_applied": repair_applied,
                "missing_segments": missing_segments,
                "role_drift_detected": role_drift_detected,
                "role_drift_reasons": role_drift_reasons,
            }

        first_attempt = _run_attempt(temperature=0.3, retry_mode=False)
        selected_attempt = first_attempt
        counter_debug["role_drift_detected"] = bool(first_attempt["role_drift_detected"])
        if first_attempt["role_drift_detected"]:
            counter_debug["retry_applied"] = True
            counter_debug["role_drift_reasons"] = first_attempt["role_drift_reasons"]
            second_attempt = _run_attempt(temperature=0.2, retry_mode=True)
            if second_attempt["role_drift_detected"]:
                return _return_fallback(
                    error_code="COUNTERARGUMENT_ROLE_DRIFT_FALLBACK",
                    error_message="role drift detected after retry",
                    extra_flags=["role_drift_fallback_used"],
                )
            selected_attempt = second_attempt
            selected_attempt["quality_flags"] = list(
                dict.fromkeys(_ensure_list_str(selected_attempt["quality_flags"]) + ["role_drift_repaired"])
            )
            selected_attempt["repair_applied"] = True
            counter_debug["error_code"] = "COUNTERARGUMENT_ROLE_DRIFT_REPAIRED"

        structured = selected_attempt["structured"]
        citation_map = selected_attempt["citation_map"]
        followup = selected_attempt["followup"]
        quality_flags = selected_attempt["quality_flags"]
        repair_applied = bool(selected_attempt["repair_applied"])
        missing_segments = _ensure_list_str(selected_attempt["missing_segments"])

        draft = _compose_counterargument_draft(structured, followup)
        counter_debug["repair_applied"] = repair_applied
        counter_debug["missing_citation_segments"] = missing_segments
        if repair_applied and not counter_debug["error_code"]:
            counter_debug["error_code"] = "COUNTERARGUMENT_REPAIRED"
        debug["counterargument"] = counter_debug

        return {
            "counterargument_structured": structured,
            "counterargument_citations": citation_map,
            "counterargument_quality_flags": list(dict.fromkeys(quality_flags)),
            "counterargument_draft": draft,
            "followup_question": followup,
            "debug": debug,
        }
    except Exception as exc:
        return _return_fallback(
            error_code="COUNTERARGUMENT_LLM_FAILED",
            error_message=str(exc),
        )


def judge_continue_or_end(state: DebateState) -> DebateState:
    round_index = _safe_int(state.get("round_index", 0), 0)
    max_rounds = _clamp(_safe_int(state.get("max_rounds", 5), 5), MIN_MAX_ROUNDS, MAX_MAX_ROUNDS)
    streak = max(0, _safe_int(state.get("no_new_argument_streak", 0), 0))
    ui_action = str(state.get("ui_action", "send")).strip().lower()

    has_new_argument = bool(state.get("parsed_claim", {}).get("has_new_argument", False))
    streak = 0 if has_new_argument else streak + 1

    should_end = False
    reason = ""
    reason_code = END_REASON_IN_PROGRESS

    if ui_action == "end":
        should_end = True
        reason = "用户点击结束辩论"
        reason_code = END_REASON_USER_ENDED
    elif round_index + 1 >= max_rounds:
        should_end = True
        reason = f"达到预设最大轮次（{max_rounds}）"
        reason_code = END_REASON_MAX_ROUNDS

    debug = _ensure_debug_dict(state.get("debug", {}))
    debug["judge"] = {
        "ui_action": ui_action,
        "round_index": round_index,
        "max_rounds": max_rounds,
        "has_new_argument": has_new_argument,
        "no_new_argument_streak": streak,
        "should_end": should_end,
        "end_reason_code": reason_code,
    }

    return {
        "no_new_argument_streak": streak,
        "should_end": should_end,
        "end_reason": reason,
        "end_reason_code": reason_code,
        "debug": debug,
    }


def ask_next_challenge(state: DebateState) -> DebateState:
    reply_views = _build_reply_views(
        counterargument_draft=state.get("counterargument_draft", ""),
        followup_question=state.get("followup_question", ""),
    )
    brief = reply_views["assistant_brief"]
    detail = reply_views["assistant_detail"]
    structured_snapshot_raw = _ensure_dict(state.get("counterargument_structured", {}))
    structured_snapshot: Dict[str, Any] = {}
    for key, value in structured_snapshot_raw.items():
        if isinstance(value, list):
            structured_snapshot[str(key)] = list(value)
        elif isinstance(value, dict):
            structured_snapshot[str(key)] = dict(value)
        else:
            structured_snapshot[str(key)] = value
    raw_citations = _ensure_dict(state.get("counterargument_citations", {}))
    citation_snapshot: Dict[str, List[str]] = {}
    for key, value in raw_citations.items():
        citation_snapshot[str(key)] = _ensure_list_str(value)
    quality_flags = _ensure_list_str(state.get("counterargument_quality_flags", []))

    history = list(state.get("debate_history", []))
    history.append(
        DebateTurn(
            round_no=state.get("round_index", 0) + 1,
            user_input=state.get("current_user_input", ""),
            parsed_summary=state.get("parsed_claim", {}).get("summary", ""),
            attack_target=state.get("attack_target", ""),
            attack_target_category=state.get("attack_target_category", ""),
            attack_target_reason=state.get("attack_target_reason", ""),
            assistant_reply=brief,
            assistant_brief=brief,
            assistant_detail=detail,
            counterargument_structured_snapshot=structured_snapshot,
            counterargument_citations_snapshot=dict(citation_snapshot),
            counterargument_quality_flags=list(quality_flags),
        )
    )

    previous = list(state.get("previous_user_inputs", []))
    current = state.get("current_user_input", "")
    if current:
        previous.append(current)

    return {
        "assistant_reply": brief,
        "assistant_brief": brief,
        "assistant_detail": detail,
        "debate_history": history,
        "previous_user_inputs": previous,
        "round_index": state.get("round_index", 0) + 1,
    }


def _safe_report_fallback(state: DebateState, end_reason: str) -> DebateReport:
    history = state.get("debate_history", [])
    parsed_summaries = [turn.get("parsed_summary", "") for turn in history if turn.get("parsed_summary")]
    attack_targets = [turn.get("attack_target", "") for turn in history if turn.get("attack_target")]
    return {
        "debate_background": state.get("case_background", ""),
        "user_claim_summary": parsed_summaries[:5],
        "defendant_rebuttal_points": attack_targets[:5],
        "user_strengths": ["能够持续参与多轮论证。"],
        "user_weaknesses": ["建议补强证据链与法条适配。"],
        "evidence_improvement_suggestions": [
            "按时间轴整理事实并为每个事实附上对应证据。",
            "补充原始证据来源，减少片段截图依赖。",
        ],
        "legal_argument_suggestions": [
            "每个诉求匹配至少一条法律依据并解释适用要件。",
            "先论证法律关系性质，再论证责任与赔偿。",
        ],
        "overall_score": 70,
        "end_reason": end_reason,
    }


def _clip_report_list(value: Any, default_items: List[str]) -> List[str]:
    items = [_clip_text(item, REPORT_ITEM_MAX_LEN) for item in _ensure_list_str(value)[:REPORT_LIST_MAX_ITEMS]]
    items = [item for item in items if item]
    if items:
        return items
    return [_clip_text(item, REPORT_ITEM_MAX_LEN) for item in default_items if _clip_text(item, REPORT_ITEM_MAX_LEN)]


def _sanitize_report_payload(
    raw_result: Dict[str, Any],
    state: DebateState,
    end_reason: str,
) -> Tuple[DebateReport, List[str], bool]:
    history = state.get("debate_history", [])
    parsed_summaries = [_clip_text(turn.get("parsed_summary", ""), REPORT_ITEM_MAX_LEN) for turn in history if turn.get("parsed_summary")]
    attack_targets = [_clip_text(turn.get("attack_target", ""), REPORT_ITEM_MAX_LEN) for turn in history if turn.get("attack_target")]

    quality_flags: List[str] = []
    repaired = False

    debate_background = _clip_text(raw_result.get("debate_background", state.get("case_background", "")), REPORT_BG_MAX_LEN)
    if not debate_background:
        debate_background = _clip_text(state.get("case_background", ""), REPORT_BG_MAX_LEN)
        repaired = True
        quality_flags.append("repaired_debate_background")

    report: DebateReport = {
        "debate_background": debate_background,
        "user_claim_summary": _clip_report_list(
            raw_result.get("user_claim_summary"),
            default_items=parsed_summaries[:3] or ["主张信息需要进一步补全。"],
        ),
        "defendant_rebuttal_points": _clip_report_list(
            raw_result.get("defendant_rebuttal_points"),
            default_items=attack_targets[:3] or ["反驳点以证据链与规则适配为主。"],
        ),
        "user_strengths": _clip_report_list(
            raw_result.get("user_strengths"),
            default_items=["能够持续参与多轮论证。"],
        ),
        "user_weaknesses": _clip_report_list(
            raw_result.get("user_weaknesses"),
            default_items=["关键事实与证据映射仍不充分。"],
        ),
        "evidence_improvement_suggestions": _clip_report_list(
            raw_result.get("evidence_improvement_suggestions"),
            default_items=[
                "按时间轴整理事实并为每个事实补充原始证据。",
                "对关键证据补充来源、真实性与关联性说明。",
            ],
        ),
        "legal_argument_suggestions": _clip_report_list(
            raw_result.get("legal_argument_suggestions"),
            default_items=[
                "为每项请求匹配明确法律依据并解释要件。",
                "先完成事实认定，再衔接规则适用与责任结论。",
            ],
        ),
        "overall_score": _clamp(_safe_int(raw_result.get("overall_score", 70), 70), 0, 100),
        "end_reason": end_reason,
    }

    if not isinstance(raw_result.get("overall_score", 70), int) and not str(raw_result.get("overall_score", "")).isdigit():
        repaired = True
        quality_flags.append("repaired_overall_score")
    elif report["overall_score"] != raw_result.get("overall_score", 70):
        repaired = True
        quality_flags.append("repaired_overall_score")

    if not _ensure_list_str(raw_result.get("user_claim_summary")):
        repaired = True
        quality_flags.append("repaired_user_claim_summary")
    if not _ensure_list_str(raw_result.get("defendant_rebuttal_points")):
        repaired = True
        quality_flags.append("repaired_defendant_rebuttal_points")

    return report, list(dict.fromkeys(quality_flags)), repaired


def generate_debate_report(state: DebateState) -> DebateState:
    end_reason = _resolve_end_reason(state)
    ui_action = str(state.get("ui_action", "send")).strip().lower()
    end_reason_code = str(state.get("end_reason_code", "")).strip()
    if end_reason_code not in (END_REASON_USER_ENDED, END_REASON_MAX_ROUNDS, END_REASON_IN_PROGRESS):
        end_reason_code = END_REASON_IN_PROGRESS
    if ui_action == "end":
        end_reason_code = END_REASON_USER_ENDED
    elif end_reason_code == END_REASON_IN_PROGRESS:
        max_rounds = _clamp(_safe_int(state.get("max_rounds", 5), 5), MIN_MAX_ROUNDS, MAX_MAX_ROUNDS)
        round_index = _safe_int(state.get("round_index", 0), 0)
        if round_index >= max_rounds:
            end_reason_code = END_REASON_MAX_ROUNDS
    debug = _ensure_debug_dict(state.get("debug", {}))
    report_debug: Dict[str, Any] = {
        "error_code": "",
        "repair_applied": False,
        "source_mode": "llm",
    }

    try:
        llm = _get_llm_client()
        result = llm.chat_json(
            system_prompt=REPORT_SYSTEM_PROMPT,
            user_prompt=build_report_user_prompt(
                case_background=state.get("case_background", ""),
                debate_history=state.get("debate_history", []),
                end_reason=end_reason,
            ),
            temperature=1.0,
        )
        if not isinstance(result, dict):
            raise ValueError("REPORT_INVALID_OUTPUT")
        report, quality_flags, repaired = _sanitize_report_payload(raw_result=result, state=state, end_reason=end_reason)
        report_debug["repair_applied"] = repaired
        if repaired:
            report_debug["error_code"] = "REPORT_REPAIRED"
        report_debug["quality_flags"] = quality_flags
        debug["report"] = report_debug
        brief, detail = _build_report_notice(end_reason=end_reason, degraded=False)
        return {
            "report": report,
            "report_source": "llm",
            "report_quality_flags": quality_flags,
            "assistant_reply": brief,
            "assistant_brief": brief,
            "assistant_detail": detail,
            "should_end": True,
            "end_reason": end_reason,
            "end_reason_code": end_reason_code,
            "debug": debug,
        }
    except Exception as exc:
        report = _safe_report_fallback(state, end_reason=end_reason)
        brief, detail = _build_report_notice(end_reason=end_reason, degraded=True)
        report_debug["source_mode"] = "fallback"
        report_debug["error_code"] = "REPORT_LLM_FAILED"
        report_debug["error_message"] = str(exc)
        report_debug["repair_applied"] = True
        quality_flags = ["fallback_used"]
        debug["report"] = report_debug
        return {
            "report": report,
            "report_source": "fallback",
            "report_quality_flags": quality_flags,
            "assistant_reply": brief,
            "assistant_brief": brief,
            "assistant_detail": detail,
            "should_end": True,
            "end_reason": end_reason,
            "end_reason_code": end_reason_code,
            "debug": debug,
        }
