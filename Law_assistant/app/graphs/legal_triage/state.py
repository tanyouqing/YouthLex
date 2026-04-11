from typing import Literal, TypedDict

from app.services.retrieval_types import LegalBasisItem, SimilarCaseItem


ScenarioValue = Literal[
    "housing",
    "labor",
    "consumer",
    "debt",
    "ip_reputation",
    "other",
]

SlotStatusValue = Literal["missing", "usable", "complete"]


class EvidenceSlots(TypedDict):
    counterparty: str | None
    time_place: str | None
    amount: str | None
    agreement: str | None
    breach_fact: str | None
    existing_evidence: list[str]


class SlotStatuses(TypedDict):
    counterparty: SlotStatusValue
    time_place: SlotStatusValue
    amount: SlotStatusValue
    agreement: SlotStatusValue
    breach_fact: SlotStatusValue
    existing_evidence: SlotStatusValue


class SlotNotes(TypedDict):
    counterparty: list[str]
    time_place: list[str]
    amount: list[str]
    agreement: list[str]
    breach_fact: list[str]
    existing_evidence: list[str]


class ConversationMessage(TypedDict):
    role: str
    content: str


class TriageState(TypedDict):
    session_id: str
    scenario: ScenarioValue
    user_input: str
    case_context: str
    conversation_history: list[ConversationMessage]
    evidence_slots: EvidenceSlots
    slot_statuses: SlotStatuses
    slot_notes: SlotNotes
    missing_slots: list[str]
    legal_basis: list[LegalBasisItem]
    legal_basis_notes: list[str]
    action_steps: list[str]
    demand_letter: str
    similar_cases: list[SimilarCaseItem]
    current_stage: str
    assistant_message: str
    empathy_message: str
    legal_grounding_message: str
    intro_completed: bool
    requested_slot: str | None
    unavailable_slots: list[str]
    awaiting_confirmation: bool
    finalized_once: bool


def empty_evidence_slots() -> EvidenceSlots:
    return {
        "counterparty": None,
        "time_place": None,
        "amount": None,
        "agreement": None,
        "breach_fact": None,
        "existing_evidence": [],
    }


def empty_slot_statuses() -> SlotStatuses:
    return {
        "counterparty": "missing",
        "time_place": "missing",
        "amount": "missing",
        "agreement": "missing",
        "breach_fact": "missing",
        "existing_evidence": "missing",
    }


def empty_slot_notes() -> SlotNotes:
    return {
        "counterparty": [],
        "time_place": [],
        "amount": [],
        "agreement": [],
        "breach_fact": [],
        "existing_evidence": [],
    }
