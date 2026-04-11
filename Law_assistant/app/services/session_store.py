from __future__ import annotations

from copy import deepcopy
from threading import Lock

from app.graphs.legal_triage.state import TriageState


class InMemorySessionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._data: dict[str, TriageState] = {}

    def get(self, session_id: str) -> TriageState | None:
        with self._lock:
            value = self._data.get(session_id)
            return deepcopy(value) if value is not None else None

    def set(self, session_id: str, state: TriageState) -> None:
        with self._lock:
            self._data[session_id] = deepcopy(state)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_session_store = InMemorySessionStore()


def get_session_store() -> InMemorySessionStore:
    return _session_store
