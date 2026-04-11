from __future__ import annotations

from app.graphs.legal_triage.state import EvidenceSlots, TriageState
from app.schemas.triage import (
    AssistantTurnModel,
    ConversationMessageModel,
    FrontendGuidanceModel,
    StageProgressModel,
    TriageResponse,
    TriageSidebar,
)
from app.services.legal_workflows import SCENARIO_META


STAGE_SEQUENCE = [
    "empathy",
    "legal_grounding",
    "slot_filling",
    "action_plan",
    "deliverables",
]

SLOT_LABELS = {
    "counterparty": "相对方信息",
    "time_place": "时间地点",
    "amount": "标的金额",
    "agreement": "合同约定",
    "breach_fact": "违约事实",
    "existing_evidence": "现有证据",
}

FOLLOW_UP_QUESTIONS = {
    "counterparty": "请补充对方是谁。店名、公司名、平台名或房东/中介信息，哪怕你现在只记得一个称呼也可以。",
    "time_place": "事情大概发生在什么时候、什么地点？如果只记得其中一部分，也可以先补时间或地点。",
    "amount": "这次纠纷大概涉及多少钱、押金、工资、退款金额或损失金额？先说大概数字、约数或费用项也可以。",
    "agreement": "你们当时是怎么约定的？合同、聊天承诺、口头约定、平台规则或菜单说明都可以。",
    "breach_fact": "对方具体做了什么违约、侵权或拒不履行的行为？按你的话描述就可以。",
    "existing_evidence": "你手上已经有什么证据？聊天截图、转账记录、订单、小票、照片、视频、病历、录音或链接都可以。",
}


def build_triage_response(state: TriageState) -> TriageResponse:
    return TriageResponse(
        session_id=state["session_id"],
        scenario=state["scenario"],
        scenario_label=SCENARIO_META[state["scenario"]]["label"],
        assistant_message=state["assistant_message"],
        current_stage=state["current_stage"],
        assistant_turn=AssistantTurnModel(
            content=state["assistant_message"],
            stage=state["current_stage"],
        ),
        conversation_history=[
            ConversationMessageModel(role=message["role"], content=message["content"])
            for message in state["conversation_history"]
        ],
        progress=_build_stage_progress(state),
        frontend=_build_frontend_guidance(state),
        sidebar=TriageSidebar(
            evidence_slots=state["evidence_slots"],
            action_steps=state["action_steps"],
            demand_letter=state["demand_letter"],
            similar_cases=state["similar_cases"],
        ),
    )


def _build_stage_progress(state: TriageState) -> StageProgressModel:
    collected_slots = _collected_slots(state["evidence_slots"])
    total_slots = len(SLOT_LABELS)
    evidence_completion_ratio = round(len(collected_slots) / total_slots, 2)
    deliverables_ready = bool(
        state["demand_letter"] and state["action_steps"] and state["similar_cases"]
    )

    if state["current_stage"] == "slot_filling" and not deliverables_ready:
        completed_stages = ["empathy", "legal_grounding", "slot_filling"]
        remaining_stages = ["slot_filling", "action_plan", "deliverables"]
        next_stage = "slot_filling"
    else:
        current_index = STAGE_SEQUENCE.index(state["current_stage"])
        completed_stages = STAGE_SEQUENCE[: current_index + 1]
        remaining_stages = STAGE_SEQUENCE[current_index + 1 :]
        next_stage = remaining_stages[0] if remaining_stages else None

    return StageProgressModel(
        current_stage=state["current_stage"],
        completed_stages=completed_stages,
        remaining_stages=remaining_stages,
        next_stage=next_stage,
        collected_slots=collected_slots,
        missing_slots=state["missing_slots"],
        evidence_completion_ratio=evidence_completion_ratio,
        evidence_complete=not state["missing_slots"],
        deliverables_ready=deliverables_ready,
    )


def _build_frontend_guidance(state: TriageState) -> FrontendGuidanceModel:
    requested_slot = state["requested_slot"]
    missing_slots = state["missing_slots"]

    if state["demand_letter"]:
        display_mode = "deliverables_ready"
        primary_panel = "demand_letter"
        input_placeholder = "可以继续补充新事实，系统会自动更新总结和交付物"
        follow_up_questions = []
        suggested_actions = [
            "复制催告函",
            "按维权步骤继续推进",
        ]
    elif state["current_stage"] == "slot_filling" or missing_slots:
        display_mode = "slot_collection"
        primary_panel = "evidence_slots"
        if requested_slot and requested_slot in FOLLOW_UP_QUESTIONS:
            input_placeholder = _build_input_placeholder(requested_slot)
            follow_up_questions = [FOLLOW_UP_QUESTIONS[requested_slot]]
            suggested_actions = [
                "回答当前这一项",
                "整理对应证据后再补充",
            ]
        else:
            input_placeholder = "如果准备好了，可直接回复“开始整理”；也可以继续补充新信息"
            follow_up_questions = ["如果你没有更多要补充的，可以直接回复“开始整理”。"]
            suggested_actions = [
                "回复“开始整理”",
                "继续补充遗漏信息",
            ]
    else:
        display_mode = "action_guidance"
        primary_panel = "action_steps"
        input_placeholder = "补充更多细节，系统会继续完善方案"
        follow_up_questions = []
        suggested_actions = [
            "查看行动步骤",
            "继续补充案情",
        ]

    return FrontendGuidanceModel(
        display_mode=display_mode,
        primary_panel=primary_panel,
        input_placeholder=input_placeholder,
        follow_up_questions=follow_up_questions,
        suggested_actions=suggested_actions,
    )


def _collected_slots(evidence_slots: EvidenceSlots) -> list[str]:
    collected: list[str] = []
    for slot_name in SLOT_LABELS:
        value = evidence_slots[slot_name]
        if slot_name == "existing_evidence":
            if value:
                collected.append(slot_name)
            continue
        if value:
            collected.append(slot_name)
    return collected


def _build_input_placeholder(slot_name: str) -> str:
    placeholders = {
        "counterparty": "请补充对方身份，如姓名、公司名、店名、平台名或房东/中介信息",
        "time_place": "请补充事情发生的时间、地点；如果只记得其中一部分，也可以先告诉我",
        "amount": "请补充涉及金额，可以是大概数字、约数，或按费用项来描述",
        "agreement": "请补充双方约定内容，如合同条款、聊天承诺、平台规则或菜单说明",
        "breach_fact": "请补充对方具体做了什么违约或侵权行为，按你的话描述即可",
        "existing_evidence": "请补充你手头已有的证据，如截图、转账记录、小票、视频、病历或录音等",
    }
    return placeholders.get(slot_name, "继续补充与你维权相关的关键信息")
