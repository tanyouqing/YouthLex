from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Body, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import APIError, SessionNotFoundError
from app.api.mappers import state_to_session_summary
from app.api.models import (
    CreateSessionRequest,
    ErrorResponseModel,
    HealthResponseModel,
    SessionEnvelopeModel,
    TurnRequest,
)
from app.api.store import SessionStore
from app.graph.builder import build_debate_graph
from app.graph.nodes.debate_nodes import init_session
from app.graph.schemas.state import DebateState


GRAPH_RECURSION_LIMIT = 100
SESSION_TTL_SECONDS = 24 * 3600

_GRAPH = None
_SESSION_STORE = SessionStore(ttl_seconds=SESSION_TTL_SECONDS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:12]}"


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_debate_graph()
    return _GRAPH


def _build_initial_state(session_id: str, payload: CreateSessionRequest) -> DebateState:
    base_state: DebateState = {
        "session_id": session_id,
        "case_background": payload.case_background,
        "scenario_hint": payload.scenario_hint,
        "max_rounds": payload.max_rounds,
        "round_index": 0,
        "debate_history": [],
        "previous_user_inputs": [],
        "current_user_input": "",
        "ui_action": "send",
        "debug": {},
    }
    normalized = init_session(base_state)
    merged = dict(base_state)
    merged.update(normalized)
    merged["session_id"] = session_id
    merged["case_background"] = payload.case_background
    merged["scenario_hint"] = payload.scenario_hint
    merged["ui_action"] = "send"
    merged["current_user_input"] = ""
    return merged


def _to_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponseModel(
        error={
            "code": code,
            "message": message,
            "details": details,
        },
        trace_id=_new_trace_id(),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _normalize_turn_user_text(action: str, user_text: str) -> str:
    if action == "end":
        return ""
    return str(user_text or "").strip()


def _reset_runtime_for_tests(ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
    global _GRAPH, _SESSION_STORE
    _GRAPH = None
    _SESSION_STORE = SessionStore(ttl_seconds=ttl_seconds)


def create_app() -> FastAPI:
    application = FastAPI(title="Debate Partner API", version="v1")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(APIError)
    def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        return _to_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @application.exception_handler(RequestValidationError)
    def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _to_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_ARGUMENT",
            message="request validation failed",
            details={"errors": exc.errors()},
        )

    @application.exception_handler(Exception)
    def unhandled_error_handler(_: Request, __: Exception) -> JSONResponse:
        return _to_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="internal server error",
            details=None,
        )

    @application.get("/api/v1/health", response_model=HealthResponseModel)
    def get_health() -> HealthResponseModel:
        return HealthResponseModel(
            status="ok",
            service="debate-agent",
            version="v1",
            timestamp=_now(),
        )

    @application.post(
        "/api/v1/sessions",
        status_code=status.HTTP_201_CREATED,
        response_model=SessionEnvelopeModel,
    )
    def create_session(payload: CreateSessionRequest | None = Body(default=None)) -> SessionEnvelopeModel:
        req = payload or CreateSessionRequest()
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        initial_state = _build_initial_state(session_id=session_id, payload=req)
        _, state, updated_at = _SESSION_STORE.create(initial_state)
        summary = state_to_session_summary(state=state, updated_at=updated_at)
        return SessionEnvelopeModel(session=summary)

    @application.get("/api/v1/sessions/{session_id}", response_model=SessionEnvelopeModel)
    def get_session(session_id: str) -> SessionEnvelopeModel:
        try:
            state, updated_at = _SESSION_STORE.get(session_id=session_id)
        except SessionNotFoundError:
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SESSION_NOT_FOUND",
                message="session_id does not exist",
                details={"session_id": session_id},
            ) from None
        summary = state_to_session_summary(state=state, updated_at=updated_at)
        return SessionEnvelopeModel(session=summary)

    @application.post("/api/v1/sessions/{session_id}/turn", response_model=SessionEnvelopeModel)
    def run_turn(session_id: str, payload: TurnRequest) -> SessionEnvelopeModel:
        action = str(payload.action).strip().lower()
        user_text = _normalize_turn_user_text(action=action, user_text=payload.user_text)
        if action == "send" and not user_text:
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_ARGUMENT",
                message="send action requires non-empty user_text",
                details={"field": "user_text"},
            )

        def turn_fn(current_state: DebateState) -> DebateState:
            if action == "send" and bool(current_state.get("should_end", False)):
                raise APIError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="SESSION_ALREADY_ENDED",
                    message="cannot send new turn after session ended",
                    details={"session_id": session_id},
                )

            invoke_state: DebateState = copy.deepcopy(current_state)
            invoke_state["ui_action"] = "end" if action == "end" else "send"
            invoke_state["current_user_input"] = user_text
            result: DebateState = _get_graph().invoke(
                invoke_state,
                config={"recursion_limit": GRAPH_RECURSION_LIMIT},
            )
            result["session_id"] = current_state.get("session_id", session_id)
            result["case_background"] = current_state.get("case_background", "")
            result["scenario_hint"] = current_state.get("scenario_hint", "")
            return result

        try:
            state, updated_at = _SESSION_STORE.run_turn(session_id=session_id, turn_fn=turn_fn)
        except SessionNotFoundError:
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SESSION_NOT_FOUND",
                message="session_id does not exist",
                details={"session_id": session_id},
            ) from None
        summary = state_to_session_summary(state=state, updated_at=updated_at)
        return SessionEnvelopeModel(session=summary)

    return application


app = create_app()

