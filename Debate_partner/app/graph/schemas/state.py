from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict


RecordType = Literal["statute", "case", "issue_rule", "rebuttal_template", "synthetic_support"]
UIAction = Literal["send", "end"]
ParseSource = Literal["llm", "fallback", "skipped"]
AttackTargetCategory = Literal[
    "法律依据不足",
    "证据链薄弱",
    "因果链不完整",
    "损失计算不充分",
    "规则适用错误",
    "程序或主体适格瑕疵",
    "论点信息不足",
]
AttackTargetSource = Literal["llm", "fallback", "reranked"]


class ParsedClaim(TypedDict, total=False):
    summary: str
    claims: List[str]
    evidence: List[str]
    legal_basis: List[str]
    request: str
    has_new_argument: bool
    parse_source: ParseSource


class KnowledgeHit(TypedDict, total=False):
    record_id: str
    record_type: RecordType
    score: int
    citation: str
    snippet: str


class DebateTurn(TypedDict, total=False):
    round_no: int
    user_input: str
    parsed_summary: str
    attack_target: str
    attack_target_category: AttackTargetCategory
    attack_target_reason: str
    assistant_reply: str
    assistant_brief: str
    assistant_detail: str
    counterargument_structured_snapshot: Dict[str, Any]
    counterargument_citations_snapshot: Dict[str, List[str]]
    counterargument_quality_flags: List[str]


class DebateReport(TypedDict, total=False):
    debate_background: str
    user_claim_summary: List[str]
    defendant_rebuttal_points: List[str]
    user_strengths: List[str]
    user_weaknesses: List[str]
    evidence_improvement_suggestions: List[str]
    legal_argument_suggestions: List[str]
    overall_score: int
    end_reason: str


class DebateState(TypedDict, total=False):
    session_id: str
    case_background: str
    scenario_hint: str

    max_rounds: int
    round_index: int
    current_user_input: str
    normalized_user_input: str
    ui_action: UIAction
    input_valid: bool
    input_error_code: str
    input_error_message: str

    parsed_claim: ParsedClaim
    attack_target: str
    attack_target_category: AttackTargetCategory
    attack_target_reason: str
    attack_target_source: AttackTargetSource
    retrieved_knowledge: List[KnowledgeHit]
    retrieval_mode: Literal["vector", "keyword_fallback"]
    knowledge_sufficiency: bool
    knowledge_missing_aspects: List[str]
    counterargument_structured: Dict[str, Any]
    counterargument_citations: Dict[str, List[str]]
    counterargument_quality_flags: List[str]
    counterargument_draft: str
    followup_question: str
    assistant_reply: str
    assistant_brief: str
    assistant_detail: str

    debate_history: List[DebateTurn]
    previous_user_inputs: List[str]
    no_new_argument_streak: int

    should_end: bool
    end_reason: str
    end_reason_code: str

    report: DebateReport
    report_source: Literal["llm", "fallback"]
    report_quality_flags: List[str]
    debug: Dict[str, Any]
