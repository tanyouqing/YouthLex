import logging
from time import perf_counter

from app.graphs.legal_triage.state import TriageState
from app.services.delilegal_client import (
    DeliLegalAPIError,
    DeliLegalConfigError,
    DeliLegalHTTPError,
    DeliLegalResponseError,
    DeliLegalTransportError,
)
from app.services.evidence_extractor import (
    build_case_context,
    choose_next_slot,
    compute_missing_slots,
    slot_has_value,
)
from app.services.legal_workflows import (
    SCENARIO_META,
    build_action_plan,
    build_demand_letter,
    build_legal_basis_notes,
    format_similar_cases_for_sidebar,
)
from app.services.llm_client import get_legal_triage_llm
from app.services.knowledge_base import LegalKnowledgeBase

logger = logging.getLogger(__name__)

SLOT_LABELS = {
    "counterparty": "相对方信息",
    "time_place": "时间地点",
    "amount": "标的金额",
    "agreement": "合同约定",
    "breach_fact": "违约事实",
    "existing_evidence": "现有证据",
}

FOLLOW_UP_QUESTIONS = {
    "counterparty": "请先告诉我对方是谁。店名、公司名、平台名、房东/中介身份，哪怕你现在只记得一个称呼也可以，我先帮你整理。",
    "time_place": "事情大概发生在什么时候、什么地点？哪怕你现在只记得时间或地点中的一部分，也可以先告诉我。",
    "amount": "这次纠纷大概涉及多少钱、押金、工资、退款金额或损失金额？先说一个大概数字、约数，或者有哪些费用项，我来帮你整理。",
    "agreement": "你们当时是怎么约定的？合同、聊天承诺、口头约定、平台规则、菜单说明这类信息都可以先说。",
    "breach_fact": "对方具体做了什么违约、侵权或拒不履行的行为？按你的话描述就行，我来帮你整理成关键事实。",
    "existing_evidence": "你手上已经有什么证据？聊天截图、转账记录、订单、小票、照片、视频、病历、录音这类都可以先告诉我。",
}


def _log_node_end(node_name: str, state: TriageState, start_time: float, **extra: object) -> None:
    duration_ms = round((perf_counter() - start_time) * 1000, 2)
    details = " ".join(f"{key}={value}" for key, value in extra.items() if value is not None)
    logger.info(
        "Node completed node=%s session_id=%s scenario=%s duration_ms=%s %s",
        node_name,
        state["session_id"],
        state["scenario"],
        duration_ms,
        details,
    )


def _classify_retrieval_error(exc: Exception) -> str:
    if isinstance(exc, DeliLegalConfigError):
        return "config_error"
    if isinstance(exc, DeliLegalTransportError):
        return "transport_error"
    if isinstance(exc, DeliLegalHTTPError):
        return "http_error"
    if isinstance(exc, DeliLegalAPIError):
        return "api_error"
    if isinstance(exc, DeliLegalResponseError):
        return "response_error"
    return "unexpected_error"


def empathy_node(state: TriageState) -> dict[str, object]:
    start_time = perf_counter()
    try:
        result = get_legal_triage_llm().generate_empathy(
            user_input=state["user_input"], scenario=state["scenario"]
        )
        empathy_message = result.assistant_message
    except Exception:
        empathy_message = "同学先别着急，我已经接住你的情况了。我们一步一步来，把能主张的依据和证据先理清。"

    _log_node_end("empathy", state, start_time)
    return {
        "current_stage": "empathy",
        "assistant_message": empathy_message,
        "empathy_message": empathy_message,
    }


def legal_grounding_node(state: TriageState) -> dict[str, object]:
    start_time = perf_counter()
    legal_basis = []
    legal_basis_notes = []
    retrieval_status = "success"
    retrieval_error_type = None

    try:
        with LegalKnowledgeBase() as knowledge_base:
            legal_basis = knowledge_base.retrieve_legal_basis(
                state["case_context"], scenario=state["scenario"]
            )
            logger.info(
                "Legal grounding retrieval completed session_id=%s query=%s result_count=%s",
                state["session_id"],
                getattr(knowledge_base, "last_legal_query", None),
                len(legal_basis),
            )
        if not legal_basis:
            retrieval_status = "empty"
    except Exception as exc:
        retrieval_status = "unavailable"
        retrieval_error_type = _classify_retrieval_error(exc)
        logger.warning(
            "Legal grounding retrieval degraded session_id=%s error_type=%s error=%s",
            state["session_id"],
            retrieval_error_type,
            exc,
        )

    try:
        result = get_legal_triage_llm().generate_legal_grounding(
            user_input=state["case_context"],
            scenario=state["scenario"],
            legal_basis_items=legal_basis,
            retrieval_status=retrieval_status,
        )
        legal_basis_notes = result.legal_basis_notes
        legal_grounding_message = result.assistant_message
    except Exception:
        legal_basis_notes = build_legal_basis_notes(
            legal_basis_items=legal_basis,
            scenario=state["scenario"],
            retrieval_status=retrieval_status,
        )
        legal_grounding_message = _build_grounding_fallback_message(
            state["scenario"],
            retrieval_status,
            legal_basis_notes,
        )

    _log_node_end(
        "legal_grounding",
        state,
        start_time,
        retrieval_status=retrieval_status,
        retrieval_error_type=retrieval_error_type,
        legal_basis_count=len(legal_basis),
    )
    return {
        "current_stage": "legal_grounding",
        "legal_basis": legal_basis,
        "legal_basis_notes": legal_basis_notes,
        "assistant_message": legal_grounding_message,
        "legal_grounding_message": legal_grounding_message,
    }


def slot_filling_node(state: TriageState) -> dict[str, object]:
    start_time = perf_counter()
    evidence_slots = state["evidence_slots"]
    slot_statuses = state.get("slot_statuses")
    missing_slots = compute_missing_slots(evidence_slots, slot_statuses)
    unavailable_slots = [slot for slot in state["unavailable_slots"] if slot in missing_slots]
    next_requested_slot = choose_next_slot(missing_slots, unavailable_slots)
    awaiting_confirmation = next_requested_slot is None
    case_context = build_case_context(state["conversation_history"], evidence_slots)
    assistant_message = _build_slot_filling_message(
        state=state,
        missing_slots=missing_slots,
        unavailable_slots=unavailable_slots,
        next_requested_slot=next_requested_slot,
    )

    _log_node_end(
        "slot_filling",
        state,
        start_time,
        missing_slots=len(missing_slots),
        unavailable_slots=len(unavailable_slots),
    )
    return {
        "current_stage": "slot_filling",
        "missing_slots": missing_slots,
        "evidence_slots": evidence_slots,
        "case_context": case_context,
        "assistant_message": assistant_message,
        "intro_completed": True,
        "requested_slot": next_requested_slot,
        "unavailable_slots": unavailable_slots,
        "awaiting_confirmation": awaiting_confirmation,
    }


def action_plan_node(state: TriageState) -> dict[str, object]:
    start_time = perf_counter()
    fallback_action_steps = build_action_plan(
        scenario=state["scenario"],
        evidence_slots=state["evidence_slots"],
        missing_slots=state["missing_slots"],
        legal_basis_notes=state["legal_basis_notes"],
    )

    try:
        result = get_legal_triage_llm().generate_action_plan(
            user_input=state["case_context"],
            scenario=state["scenario"],
            evidence_slots=state["evidence_slots"],
            missing_slots=state["missing_slots"],
            legal_basis_notes=state["legal_basis_notes"],
            suggested_steps=fallback_action_steps,
        )
        action_steps = result.action_steps or fallback_action_steps
        assistant_message = result.assistant_message
    except Exception:
        action_steps = fallback_action_steps
        assistant_message = "我已经按你当前的纠纷类型和证据情况整理出一版可直接执行的维权步骤。"

    _log_node_end("action_plan", state, start_time, action_steps=len(action_steps))
    return {
        "current_stage": "action_plan",
        "action_steps": action_steps,
        "assistant_message": assistant_message,
    }


def deliverables_node(state: TriageState) -> dict[str, object]:
    start_time = perf_counter()
    retrieved_similar_cases = []
    retrieval_status = "success"
    retrieval_error_type = None

    try:
        with LegalKnowledgeBase() as knowledge_base:
            retrieved_similar_cases = knowledge_base.retrieve_similar_cases(
                state["case_context"], scenario=state["scenario"]
            )
            logger.info(
                "Deliverables retrieval completed session_id=%s query=%s result_count=%s",
                state["session_id"],
                getattr(knowledge_base, "last_case_query", None),
                len(retrieved_similar_cases),
            )
        if not retrieved_similar_cases:
            retrieval_status = "empty"
    except Exception as exc:
        retrieval_status = "unavailable"
        retrieval_error_type = _classify_retrieval_error(exc)
        logger.warning(
            "Deliverables retrieval degraded session_id=%s error_type=%s error=%s",
            state["session_id"],
            retrieval_error_type,
            exc,
        )

    formatted_similar_cases = format_similar_cases_for_sidebar(
        similar_case_items=retrieved_similar_cases,
        scenario=state["scenario"],
    )
    fallback_demand_letter = build_demand_letter(
        scenario=state["scenario"],
        evidence_slots=state["evidence_slots"],
        legal_basis_notes=state["legal_basis_notes"],
        action_steps=state["action_steps"],
    )

    base_summary = ""
    try:
        result = get_legal_triage_llm().generate_deliverables(
            user_input=state["case_context"],
            scenario=state["scenario"],
            action_steps=state["action_steps"],
            legal_basis_items=state["legal_basis"],
            legal_basis_notes=state["legal_basis_notes"],
            similar_case_items=retrieved_similar_cases,
            retrieval_status=retrieval_status,
            evidence_slots=state["evidence_slots"],
            draft_demand_letter=fallback_demand_letter,
        )
        demand_letter = result.demand_letter or fallback_demand_letter
        base_summary = result.assistant_message

        if formatted_similar_cases:
            similar_cases = formatted_similar_cases
        else:
            similar_cases = [case.model_dump() for case in result.similar_cases]
    except Exception:
        demand_letter = fallback_demand_letter
        if formatted_similar_cases:
            similar_cases = formatted_similar_cases
            base_summary = "我已经结合检索到的相似案例整理好了本次维权交付物。"
        elif retrieval_status == "empty":
            similar_cases = [
                {
                    "title": "示例案例占位",
                    "summary": "暂未检索到足够相似的真实案例，后续可补充更具体案情后再次检索。",
                    "judgment": "待补充。",
                    "takeaway": "当前可先依赖催告函和行动步骤推进维权。",
                }
            ]
            base_summary = "我先为你整理了可直接使用的维权说明和催告函，相似案例后续还可以继续补检索。"
        else:
            similar_cases = [
                {
                    "title": "示例案例占位",
                    "summary": "法律案例检索暂不可用，后续恢复后可补充真实相似案例。",
                    "judgment": "待补充。",
                    "takeaway": "当前可先依据已整理的行动步骤和催告函推进维权。",
                }
            ]
            base_summary = "案例检索暂时不可用，但我已经先帮你整理好催告函和行动建议。"

    if not similar_cases:
        similar_cases = [
            {
                "title": "示例案例占位",
                "summary": "当前未返回案例，后续可接入真实案例库。",
                "judgment": "待补充。",
                "takeaway": "待补充。",
            }
        ]

    assistant_message = _build_final_turn_message(
        state=state,
        base_summary=base_summary,
    )

    _log_node_end(
        "deliverables",
        state,
        start_time,
        retrieval_status=retrieval_status,
        retrieval_error_type=retrieval_error_type,
        similar_cases=len(similar_cases),
    )
    return {
        "current_stage": "deliverables",
        "demand_letter": demand_letter,
        "similar_cases": similar_cases,
        "assistant_message": assistant_message,
        "requested_slot": None,
        "awaiting_confirmation": False,
        "finalized_once": True,
    }


def _build_grounding_fallback_message(
    scenario: str,
    retrieval_status: str,
    legal_basis_notes: list[str],
) -> str:
    intro = f"从你目前描述的情况看，这属于“{SCENARIO_META[scenario]['label']}”范围内可继续主张的纠纷。"
    if retrieval_status == "empty":
        intro = f"从你目前描述的情况看，这件事大概率属于“{SCENARIO_META[scenario]['label']}”范围，但暂未检索到足够贴合的法规结果。"
    if retrieval_status == "unavailable":
        intro = f"从你目前描述的情况看，这件事大概率属于“{SCENARIO_META[scenario]['label']}”范围；法律检索暂不可用，我先按一般规则给你谨慎判断。"

    if not legal_basis_notes:
        return intro

    notes = "\n".join(f"- {note}" for note in legal_basis_notes[:2])
    return f"{intro}\n{notes}"


def _build_slot_filling_message(
    state: TriageState,
    missing_slots: list[str],
    unavailable_slots: list[str],
    next_requested_slot: str | None,
) -> str:
    prompt_message = _build_collection_prompt(
        missing_slots=missing_slots,
        unavailable_slots=unavailable_slots,
        next_requested_slot=next_requested_slot,
    )

    if not state["intro_completed"]:
        legal_message = _decorate_intro_grounding_message(
            state["legal_grounding_message"],
            state["legal_basis_notes"],
        )
        return "\n\n".join(
            part
            for part in [state["empathy_message"], legal_message, prompt_message]
            if part
        )

    acknowledgement = _build_collection_acknowledgement(
        requested_slot=state["requested_slot"],
        evidence_slots=state["evidence_slots"],
        slot_statuses=state.get("slot_statuses", {}),
        missing_slots=missing_slots,
        unavailable_slots=unavailable_slots,
    )
    return "\n\n".join(part for part in [acknowledgement, prompt_message] if part)


def _decorate_intro_grounding_message(
    legal_grounding_message: str,
    legal_basis_notes: list[str],
) -> str:
    if not legal_basis_notes:
        return legal_grounding_message

    notes = "\n".join(f"- {note}" for note in legal_basis_notes[:2])
    if all(note in legal_grounding_message for note in legal_basis_notes[:2]):
        return legal_grounding_message
    return f"{legal_grounding_message}\n{notes}"


def _build_collection_acknowledgement(
    requested_slot: str | None,
    evidence_slots: dict[str, object],
    slot_statuses: dict[str, object],
    missing_slots: list[str],
    unavailable_slots: list[str],
) -> str:
    if requested_slot and slot_has_value(evidence_slots, requested_slot, slot_statuses):
        if slot_statuses.get(requested_slot) == "usable":
            return f"收到，这一项“{SLOT_LABELS[requested_slot]}”我先按你目前提供的信息整理好了，后续如果有更精确材料还可以继续补。"
        return f"收到，这一项“{SLOT_LABELS[requested_slot]}”我已经记下了。"

    if requested_slot and requested_slot in unavailable_slots and requested_slot in missing_slots:
        return f"好的，我记下这项“{SLOT_LABELS[requested_slot]}”目前暂时无法补充。"

    return "收到，我已经把你刚补充的信息并入当前证据链。"


def _build_collection_prompt(
    missing_slots: list[str],
    unavailable_slots: list[str],
    next_requested_slot: str | None,
) -> str:
    if next_requested_slot:
        return f"接下来我只确认一项：{FOLLOW_UP_QUESTIONS[next_requested_slot]}"

    if missing_slots:
        unavailable_labels = [SLOT_LABELS[slot] for slot in missing_slots if slot in unavailable_slots]
        message = (
            "目前能补的内容我都先记下了。"
            f"仍缺：{'、'.join(SLOT_LABELS[slot] for slot in missing_slots)}。"
        )
        if unavailable_labels:
            message += f"其中暂时无法补充的有：{'、'.join(unavailable_labels)}。"
        message += "如果这些信息暂时拿不到了，你可以直接回复“开始整理”，我会带着这些缺口给你最终总结、维权步骤、催告函和相似案例。"
        return message

    return (
        "关键信息已经基本齐了。"
        "如果你没有更多要补充的，可以直接回复“开始整理”，"
        "我来为你整理最终总结、维权步骤、催告函和相似案例。"
    )


def _build_final_turn_message(state: TriageState, base_summary: str) -> str:
    summary_parts = [base_summary.strip()] if base_summary.strip() else []

    case_summary = _build_case_summary(state)
    if case_summary:
        summary_parts.append(case_summary)

    evidence_gap_summary = _build_evidence_gap_summary(
        missing_slots=state["missing_slots"],
        unavailable_slots=state["unavailable_slots"],
        slot_statuses=state.get("slot_statuses", {}),
        slot_notes=state.get("slot_notes", {}),
    )
    if evidence_gap_summary:
        summary_parts.append(evidence_gap_summary)

    summary_parts.append("我已经为你整理好维权步骤、催告函和相似案例，可以直接查看并复制使用。")
    return "\n\n".join(summary_parts)


def _build_case_summary(state: TriageState) -> str:
    evidence_slots = state["evidence_slots"]
    summary_bits = [
        f"纠纷类型：{SCENARIO_META[state['scenario']]['label']}",
        f"核心事实：{evidence_slots['breach_fact'] or '待进一步补充'}",
    ]
    if evidence_slots["counterparty"]:
        summary_bits.append(f"相对方：{evidence_slots['counterparty']}")
    if evidence_slots["amount"]:
        summary_bits.append(f"涉及金额：{evidence_slots['amount']}")
    return "案情整理：" + "；".join(summary_bits) + "。"


def _build_evidence_gap_summary(
    missing_slots: list[str],
    unavailable_slots: list[str],
    slot_statuses: dict[str, object],
    slot_notes: dict[str, list[str]],
) -> str:
    unavailable = [slot for slot in missing_slots if slot in unavailable_slots]
    pending = [slot for slot in missing_slots if slot not in unavailable_slots]
    parts: list[str] = []

    if pending:
        parts.append("仍待补充：" + "、".join(SLOT_LABELS[slot] for slot in pending))
    if unavailable:
        parts.append("暂时无法补充：" + "、".join(SLOT_LABELS[slot] for slot in unavailable))

    soft_gap_notes: list[str] = []
    for slot_name, status in slot_statuses.items():
        if status == "usable":
            soft_gap_notes.extend(slot_notes.get(slot_name, []))
    if soft_gap_notes:
        parts.append("仍可进一步明确：" + "；".join(dict.fromkeys(soft_gap_notes)))

    if not parts:
        return ""
    return "证据补充提示：" + "；".join(parts) + "。后续如果拿到新材料，可以继续回来更新。"
