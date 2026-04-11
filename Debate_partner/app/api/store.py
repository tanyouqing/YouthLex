from __future__ import annotations

import copy
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Tuple

from app.api.errors import SessionNotFoundError
from app.graph.schemas.state import DebateState


@dataclass
class SessionEntry:
    state: DebateState
    updated_at: datetime
    expire_at: datetime
    lock: threading.RLock = field(default_factory=threading.RLock)


class SessionStore:
    def __init__(
        self,
        ttl_seconds: int = 24 * 3600,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl = timedelta(seconds=max(1, int(ttl_seconds)))
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._sessions: Dict[str, SessionEntry] = {}
        self._global_lock = threading.RLock()

    def _now(self) -> datetime:
        current = self._now_fn()
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current

    def _cleanup_expired_locked(self, now: datetime) -> None:
        expired = [sid for sid, entry in self._sessions.items() if entry.expire_at <= now]
        for sid in expired:
            del self._sessions[sid]

    def _get_entry_locked(self, session_id: str, refresh_ttl: bool) -> SessionEntry:
        now = self._now()
        self._cleanup_expired_locked(now)
        entry = self._sessions.get(session_id)
        if entry is None:
            raise SessionNotFoundError(session_id)
        if refresh_ttl:
            entry.expire_at = now + self._ttl
        return entry

    def create(self, state: DebateState) -> Tuple[str, DebateState, datetime]:
        with self._global_lock:
            now = self._now()
            self._cleanup_expired_locked(now)
            session_id = str(state.get("session_id", "")).strip() or f"session_{uuid.uuid4().hex[:12]}"
            state_copy: DebateState = copy.deepcopy(state)
            state_copy["session_id"] = session_id
            entry = SessionEntry(
                state=state_copy,
                updated_at=now,
                expire_at=now + self._ttl,
            )
            self._sessions[session_id] = entry
            return session_id, copy.deepcopy(entry.state), entry.updated_at

    def get(self, session_id: str) -> Tuple[DebateState, datetime]:
        with self._global_lock:
            entry = self._get_entry_locked(session_id=session_id, refresh_ttl=True)
            return copy.deepcopy(entry.state), entry.updated_at

    def run_turn(
        self,
        session_id: str,
        turn_fn: Callable[[DebateState], DebateState],
    ) -> Tuple[DebateState, datetime]:
        with self._global_lock:
            entry = self._get_entry_locked(session_id=session_id, refresh_ttl=True)
            session_lock = entry.lock

        with session_lock:
            with self._global_lock:
                entry = self._get_entry_locked(session_id=session_id, refresh_ttl=True)
                current_state = copy.deepcopy(entry.state)

            next_state = turn_fn(current_state)

            with self._global_lock:
                entry = self._get_entry_locked(session_id=session_id, refresh_ttl=True)
                now = self._now()
                entry.state = copy.deepcopy(next_state)
                entry.updated_at = now
                entry.expire_at = now + self._ttl
                return copy.deepcopy(entry.state), entry.updated_at

