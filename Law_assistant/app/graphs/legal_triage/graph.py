from copy import deepcopy
from functools import lru_cache
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.graphs.legal_triage.nodes import (
    action_plan_node,
    deliverables_node,
    empathy_node,
    legal_grounding_node,
    slot_filling_node,
)
from app.graphs.legal_triage.state import (
    TriageState,
    empty_evidence_slots,
)
from app.schemas.triage import TriageRequest
from app.services.evidence_extractor import (
    build_case_context,
    compute_missing_slots,
    is_explicit_finalize_request,
    is_requested_slot_unavailable,
    merge_evidence_state,
    remove_resolved_unavailable_slots,
)
from app.services.triage_planner import resolve_scenario


WELCOME_MESSAGE = "遇到维权困难了？跟我讲讲，我来帮你解决"


TRIAGE_NODE_SEQUENCE = [
    ("empathy", empathy_node),
    ("legal_grounding", legal_grounding_node),
    ("slot_filling", slot_filling_node),
    ("action_plan", action_plan_node),
    ("deliverables", deliverables_node),
]


@lru_cache(maxsize=1)
def build_graph():
    graph_builder = StateGraph(TriageState)
    for node_name, node_handler in TRIAGE_NODE_SEQUENCE:
        graph_builder.add_node(node_name, node_handler)

    graph_builder.add_edge(START, "empathy")
    graph_builder.add_edge("empathy", "legal_grounding")
    graph_builder.add_edge("legal_grounding", "slot_filling")
    graph_builder.add_edge("slot_filling", "action_plan")
    graph_builder.add_edge("action_plan", "deliverables")
    graph_builder.add_edge("deliverables", END)

    return graph_builder.compile()


def create_initial_state(request: TriageRequest) -> TriageState:
    scenario = (
        request.scenario.value
        if request.scenario
        else resolve_scenario(
            request.user_input,
            request.scenario_hint.value if request.scenario_hint else None,
        )
    )
    session_id = request.session_id or str(uuid4())
    merge_result = merge_evidence_state(
        empty_evidence_slots(),
        request.user_input,
        scenario=scenario,
    )
    evidence_slots = merge_result["evidence_slots"]
    slot_statuses = merge_result["slot_statuses"]
    slot_notes = merge_result["slot_notes"]
    conversation_history = []
    if request.scenario_hint is not None:
        conversation_history.append({"role": "assistant", "content": WELCOME_MESSAGE})
    conversation_history.append({"role": "user", "content": request.user_input})
    case_context = build_case_context(conversation_history, evidence_slots)

    return {
        "session_id": session_id,
        "scenario": scenario,
        "user_input": request.user_input,
        "case_context": case_context,
        "conversation_history": conversation_history,
        "evidence_slots": evidence_slots,
        "slot_statuses": slot_statuses,
        "slot_notes": slot_notes,
        "missing_slots": compute_missing_slots(evidence_slots, slot_statuses),
        "legal_basis": [],
        "legal_basis_notes": [],
        "action_steps": [],
        "demand_letter": "",
        "similar_cases": [],
        "current_stage": "input",
        "assistant_message": "",
        "empathy_message": "",
        "legal_grounding_message": "",
        "intro_completed": False,
        "requested_slot": None,
        "unavailable_slots": [],
        "awaiting_confirmation": False,
        "finalized_once": False,
    }


def create_next_turn_state(previous_state: TriageState, request: TriageRequest) -> TriageState:
    scenario = request.scenario.value if request.scenario else previous_state["scenario"]
    conversation_history = previous_state["conversation_history"] + [
        {"role": "user", "content": request.user_input}
    ]
    merge_result = merge_evidence_state(
        previous_state["evidence_slots"],
        request.user_input,
        scenario=scenario,
        requested_slot=previous_state.get("requested_slot"),
    )
    evidence_slots = merge_result["evidence_slots"]
    slot_statuses = merge_result["slot_statuses"]
    slot_notes = merge_result["slot_notes"]
    missing_slots = compute_missing_slots(evidence_slots, slot_statuses)
    unavailable_slots = remove_resolved_unavailable_slots(
        previous_state["unavailable_slots"],
        evidence_slots,
        slot_statuses,
    )
    requested_slot = previous_state["requested_slot"]
    if is_requested_slot_unavailable(request.user_input, requested_slot, evidence_slots, slot_statuses):
        if requested_slot and requested_slot not in unavailable_slots:
            unavailable_slots.append(requested_slot)

    case_context = build_case_context(conversation_history, evidence_slots)
    preserve_previous_outputs = previous_state["finalized_once"]

    return {
        **previous_state,
        "session_id": previous_state["session_id"],
        "scenario": scenario,
        "user_input": request.user_input,
        "case_context": case_context,
        "conversation_history": conversation_history,
        "evidence_slots": evidence_slots,
        "slot_statuses": slot_statuses,
        "slot_notes": slot_notes,
        "missing_slots": missing_slots,
        "legal_basis": [],
        "legal_basis_notes": [],
        "action_steps": previous_state["action_steps"] if preserve_previous_outputs else [],
        "demand_letter": previous_state["demand_letter"] if preserve_previous_outputs else "",
        "similar_cases": previous_state["similar_cases"] if preserve_previous_outputs else [],
        "current_stage": "input",
        "assistant_message": "",
        "empathy_message": "",
        "legal_grounding_message": "",
        "requested_slot": requested_slot,
        "unavailable_slots": unavailable_slots,
        "awaiting_confirmation": previous_state.get("awaiting_confirmation", False),
        "finalized_once": previous_state.get("finalized_once", False),
    }


def run_legal_triage(initial_state: TriageState) -> TriageState:
    final_state = deepcopy(initial_state)
    for stream_event in iterate_legal_triage(initial_state):
        final_state = stream_event["state"]
    return final_state


def iterate_legal_triage(initial_state: TriageState):
    state = deepcopy(initial_state)
    for stage_name, node_handler in determine_turn_node_sequence(state):
        yield {"event": "stage_started", "stage": stage_name, "state": deepcopy(state)}
        updates = node_handler(state)
        state = {**state, **updates}
        yield {"event": "stage_completed", "stage": stage_name, "state": deepcopy(state)}


def finalize_triage_state(state: TriageState) -> TriageState:
    final_state = deepcopy(state)
    final_state["conversation_history"] = final_state["conversation_history"] + [
        {"role": "assistant", "content": final_state["assistant_message"]}
    ]
    return final_state


def determine_turn_node_sequence(state: TriageState):
    if not state["intro_completed"]:
        return _build_sequence(["empathy", "legal_grounding", "slot_filling"])

    if state["finalized_once"] or is_explicit_finalize_request(state["user_input"]):
        return _build_sequence(["legal_grounding", "action_plan", "deliverables"])

    return _build_sequence(["slot_filling"])


def _build_sequence(stage_names: list[str]):
    node_lookup = {name: handler for name, handler in TRIAGE_NODE_SEQUENCE}
    return [(stage_name, node_lookup[stage_name]) for stage_name in stage_names]
