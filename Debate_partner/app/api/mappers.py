from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.api.models import DebateReportModel, SessionStateSummaryModel
from app.graph.schemas.state import DebateState


def _as_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _as_list(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return []
    return list(value)


def _as_list_str(value: Any) -> List[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_nonempty(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_report(value: Any) -> DebateReportModel | None:
    report_data = _as_dict(value)
    if not report_data:
        return None
    return DebateReportModel(
        debate_background=str(report_data.get("debate_background", "")),
        user_claim_summary=_as_list_str(report_data.get("user_claim_summary")),
        defendant_rebuttal_points=_as_list_str(report_data.get("defendant_rebuttal_points")),
        user_strengths=_as_list_str(report_data.get("user_strengths")),
        user_weaknesses=_as_list_str(report_data.get("user_weaknesses")),
        evidence_improvement_suggestions=_as_list_str(report_data.get("evidence_improvement_suggestions")),
        legal_argument_suggestions=_as_list_str(report_data.get("legal_argument_suggestions")),
        overall_score=max(0, min(100, _safe_int(report_data.get("overall_score", 70), 70))),
        end_reason=str(report_data.get("end_reason", "")),
    )


def state_to_session_summary(state: DebateState, updated_at: datetime) -> SessionStateSummaryModel:
    history = _as_list(state.get("debate_history", []))
    counterargument_citations_raw = _as_dict(state.get("counterargument_citations", {}))
    counterargument_citations: Dict[str, List[str]] = {
        str(key): _as_list_str(value) for key, value in counterargument_citations_raw.items()
    }

    return SessionStateSummaryModel(
        session_id=str(state.get("session_id", "")),
        case_background=str(state.get("case_background", "")),
        scenario_hint=str(state.get("scenario_hint", "")),
        max_rounds=max(1, min(20, _safe_int(state.get("max_rounds", 5), 5))),
        round_index=max(0, _safe_int(state.get("round_index", 0), 0)),
        ui_action="end" if str(state.get("ui_action", "send")).strip().lower() == "end" else "send",
        should_end=bool(state.get("should_end", False)),
        end_reason=str(state.get("end_reason", "")),
        end_reason_code=str(state.get("end_reason_code", "IN_PROGRESS") or "IN_PROGRESS"),
        assistant_brief=str(state.get("assistant_brief", "")),
        assistant_detail=str(state.get("assistant_detail", "")),
        attack_target=str(state.get("attack_target", "")),
        attack_target_category=_optional_nonempty(state.get("attack_target_category")),
        attack_target_reason=str(state.get("attack_target_reason", "")),
        attack_target_source=_optional_nonempty(state.get("attack_target_source")),
        retrieval_mode=_optional_nonempty(state.get("retrieval_mode")),
        knowledge_sufficiency=bool(state.get("knowledge_sufficiency", True)),
        knowledge_missing_aspects=_as_list_str(state.get("knowledge_missing_aspects")),
        counterargument_structured=_as_dict(state.get("counterargument_structured", {})),
        counterargument_citations=counterargument_citations,
        counterargument_quality_flags=_as_list_str(state.get("counterargument_quality_flags")),
        report_source=_optional_nonempty(state.get("report_source")),
        report_quality_flags=_as_list_str(state.get("report_quality_flags")),
        history_count=len(history),
        updated_at=updated_at,
        report=_normalize_report(state.get("report")),
    )

