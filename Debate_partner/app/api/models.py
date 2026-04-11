from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


TurnAction = Literal["send", "end"]


class CreateSessionRequest(BaseModel):
    case_background: str = Field(
        default="学生租房退租后，房东拒绝返还押金并主张维修费用。",
        max_length=4000,
    )
    scenario_hint: str = Field(default="rental_dispute", max_length=128)
    max_rounds: int = Field(default=5, ge=1, le=20)

    model_config = {"extra": "forbid"}


class TurnRequest(BaseModel):
    action: TurnAction
    user_text: str = Field(default="", max_length=4000)

    model_config = {"extra": "forbid"}


class DebateReportModel(BaseModel):
    debate_background: str = ""
    user_claim_summary: List[str] = []
    defendant_rebuttal_points: List[str] = []
    user_strengths: List[str] = []
    user_weaknesses: List[str] = []
    evidence_improvement_suggestions: List[str] = []
    legal_argument_suggestions: List[str] = []
    overall_score: int = Field(default=70, ge=0, le=100)
    end_reason: str = ""

    model_config = {"extra": "forbid"}


class SessionStateSummaryModel(BaseModel):
    session_id: str
    case_background: str
    scenario_hint: str
    max_rounds: int = Field(ge=1, le=20)
    round_index: int = Field(ge=0)
    ui_action: TurnAction
    should_end: bool
    end_reason: str
    end_reason_code: str

    assistant_brief: str
    assistant_detail: str

    attack_target: str
    attack_target_category: str | None = None
    attack_target_reason: str = ""
    attack_target_source: str | None = None

    retrieval_mode: str | None = None
    knowledge_sufficiency: bool = True
    knowledge_missing_aspects: List[str] = []

    counterargument_structured: Dict[str, Any] = {}
    counterargument_citations: Dict[str, List[str]] = {}
    counterargument_quality_flags: List[str] = []

    report_source: str | None = None
    report_quality_flags: List[str] = []

    history_count: int = Field(ge=0)
    updated_at: datetime
    report: DebateReportModel | None = None

    model_config = {"extra": "forbid"}


class SessionEnvelopeModel(BaseModel):
    session: SessionStateSummaryModel

    model_config = {"extra": "forbid"}


class ErrorBodyModel(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class ErrorResponseModel(BaseModel):
    error: ErrorBodyModel
    trace_id: str

    model_config = {"extra": "forbid"}


class HealthResponseModel(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "debate-agent"
    version: str = "v1"
    timestamp: datetime

    model_config = {"extra": "forbid"}

