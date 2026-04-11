from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class APIError(Exception):
    status_code: int
    code: str
    message: str
    details: Dict[str, Any] | None = None


class SessionNotFoundError(KeyError):
    pass

