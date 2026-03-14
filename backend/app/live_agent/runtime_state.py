from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from .schemas import LiveSessionProfile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class LiveSessionRecord:
    session_id: str
    profile: LiveSessionProfile
    transport: str
    opened_at: datetime = field(default_factory=_utcnow)
    last_activity_at: datetime = field(default_factory=_utcnow)
    inbound: Counter[str] = field(default_factory=Counter)
    outbound: Counter[str] = field(default_factory=Counter)
    closed_at: datetime | None = None

    def note_inbound(self, message_type: str) -> None:
        self.inbound[message_type] += 1
        self.last_activity_at = _utcnow()

    def note_outbound(self, event_type: str) -> None:
        self.outbound[event_type] += 1
        self.last_activity_at = _utcnow()

    def close(self) -> None:
        self.closed_at = _utcnow()
        self.last_activity_at = self.closed_at

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.profile.mode,
            "instrument": self.profile.instrument,
            "piece": self.profile.piece,
            "goal": self.profile.goal,
            "camera_expected": self.profile.camera_expected,
            "transport": self.transport,
            "opened_at": self.opened_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "inbound": dict(self.inbound),
            "outbound": dict(self.outbound),
        }


class LiveRuntimeRegistry:
    """In-memory diagnostics store for active and recent live sessions."""

    def __init__(self, *, recent_limit: int = 12) -> None:
        self._active: dict[str, LiveSessionRecord] = {}
        self._recent: deque[LiveSessionRecord] = deque(maxlen=recent_limit)
        self._lock = Lock()

    def start_session(self, session_id: str, profile: LiveSessionProfile, transport: str) -> LiveSessionRecord:
        record = LiveSessionRecord(session_id=session_id, profile=profile, transport=transport)
        with self._lock:
            self._active[session_id] = record
        return record

    def note_inbound(self, session_id: str, message_type: str) -> None:
        with self._lock:
            record = self._active.get(session_id)
            if record is not None:
                record.note_inbound(message_type)

    def note_outbound(self, session_id: str, event_type: str) -> None:
        with self._lock:
            record = self._active.get(session_id)
            if record is not None:
                record.note_outbound(event_type)

    def end_session(self, session_id: str) -> None:
        with self._lock:
            record = self._active.pop(session_id, None)
            if record is None:
                return
            record.close()
            self._recent.appendleft(record)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            active = [record.snapshot() for record in self._active.values()]
            recent = [record.snapshot() for record in self._recent]
        return {
            "active_session_count": len(active),
            "active_sessions": active,
            "recent_sessions": recent,
        }
