import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.graphs.legal_triage.graph import (
    create_initial_state,
    create_next_turn_state,
    finalize_triage_state,
    iterate_legal_triage,
    run_legal_triage,
)
from app.schemas.triage import TriageRequest, TriageResponse
from app.services.frontend_adapter import build_triage_response
from app.services.session_store import get_session_store

router = APIRouter(prefix="/api/v1/triage", tags=["triage"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=TriageResponse)
def run_triage(request: TriageRequest) -> TriageResponse:
    initial_state = _resolve_initial_state(request)
    final_state = run_legal_triage(initial_state)
    persisted_state = _persist_final_state(final_state)
    logger.info(
        "Triage request completed session_id=%s scenario=%s stage=%s",
        persisted_state["session_id"],
        persisted_state["scenario"],
        persisted_state["current_stage"],
    )
    return build_triage_response(persisted_state)


@router.post("/stream")
def stream_triage(request: TriageRequest) -> StreamingResponse:
    initial_state = _resolve_initial_state(request)

    def event_stream() -> Iterator[str]:
        yield _format_sse_event(
            "session",
            {
                "session_id": initial_state["session_id"],
                "scenario": initial_state["scenario"],
            },
        )

        latest_state = initial_state
        try:
            for stream_event in iterate_legal_triage(initial_state):
                latest_state = stream_event["state"]
                if stream_event["event"] == "stage_started":
                    payload = {
                        "stage": stream_event["stage"],
                        "session_id": latest_state["session_id"],
                    }
                else:
                    payload = _build_stage_event_payload(stream_event["stage"], latest_state)
                yield _format_sse_event(stream_event["event"], payload)

            persisted_state = _persist_final_state(latest_state)
            logger.info(
                "Triage stream completed session_id=%s scenario=%s stage=%s",
                persisted_state["session_id"],
                persisted_state["scenario"],
                persisted_state["current_stage"],
            )
            yield _format_sse_event(
                "complete",
                {"response": build_triage_response(persisted_state).model_dump(mode="json")},
            )
        except Exception as exc:
            logger.exception(
                "Triage stream failed session_id=%s scenario=%s error=%s",
                latest_state["session_id"],
                latest_state["scenario"],
                exc,
            )
            yield _format_sse_event(
                "error",
                {
                    "message": "流式处理过程中发生异常，请改用同步接口重试，或重新发起一次会话。",
                    "session_id": latest_state["session_id"],
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _resolve_initial_state(request: TriageRequest):
    session_store = get_session_store()
    previous_state = session_store.get(request.session_id) if request.session_id else None
    logger.info(
        "Triage request received session_id=%s has_previous_state=%s scenario=%s",
        request.session_id,
        previous_state is not None,
        request.scenario.value if request.scenario else None,
    )
    if previous_state is not None:
        return create_next_turn_state(previous_state, request)
    return create_initial_state(request)


def _persist_final_state(final_state):
    persisted_state = finalize_triage_state(final_state)
    get_session_store().set(persisted_state["session_id"], persisted_state)
    return persisted_state


def _build_stage_event_payload(stage: str, state: dict[str, object]) -> dict[str, object]:
    response = build_triage_response(state).model_dump(mode="json")
    return {
        "stage": stage,
        "session_id": response["session_id"],
        "assistant_turn": response["assistant_turn"],
        "progress": response["progress"],
        "frontend": response["frontend"],
        "sidebar": response["sidebar"],
    }


def _format_sse_event(event_name: str, payload: dict[str, object]) -> str:
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {serialized_payload}\n\n"


@router.get("/session/{session_id}", response_model=TriageResponse)
def get_triage_session(session_id: str) -> TriageResponse:
    session_store = get_session_store()
    state = session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(
        "Triage session fetched session_id=%s scenario=%s stage=%s",
        state["session_id"],
        state["scenario"],
        state["current_stage"],
    )
    return build_triage_response(state)
