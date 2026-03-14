from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from threading import Lock
from typing import Any

from .schemas import LiveSessionProfile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _duration_ms(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int(round((end - start).total_seconds() * 1000)))


@dataclass(slots=True)
class LivePingPongTurn:
    turn_index: int
    speech_started_at: datetime | None
    user_turn_ended_at: datetime
    audio_chunk_count: int
    status: str = "pending"
    user_transcript_partial: str | None = None
    user_transcript_final: str | None = None
    assistant_turn_id: str | None = None
    first_assistant_event_at: datetime | None = None
    first_assistant_transcript_at: datetime | None = None
    first_assistant_audio_at: datetime | None = None
    first_assistant_text_at: datetime | None = None
    assistant_turn_completed_at: datetime | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "status": self.status,
            "speech_started_at": self.speech_started_at.isoformat() if self.speech_started_at else None,
            "user_turn_ended_at": self.user_turn_ended_at.isoformat(),
            "audio_chunk_count": self.audio_chunk_count,
            "user_transcript_partial": self.user_transcript_partial,
            "user_transcript_final": self.user_transcript_final,
            "assistant_turn_id": self.assistant_turn_id,
            "first_assistant_event_at": (
                self.first_assistant_event_at.isoformat() if self.first_assistant_event_at else None
            ),
            "first_assistant_transcript_at": (
                self.first_assistant_transcript_at.isoformat() if self.first_assistant_transcript_at else None
            ),
            "first_assistant_audio_at": (
                self.first_assistant_audio_at.isoformat() if self.first_assistant_audio_at else None
            ),
            "first_assistant_text_at": self.first_assistant_text_at.isoformat() if self.first_assistant_text_at else None,
            "assistant_turn_completed_at": (
                self.assistant_turn_completed_at.isoformat() if self.assistant_turn_completed_at else None
            ),
            "first_response_ms": _duration_ms(self.user_turn_ended_at, self.first_assistant_event_at),
            "first_transcript_ms": _duration_ms(self.user_turn_ended_at, self.first_assistant_transcript_at),
            "first_audio_ms": _duration_ms(self.user_turn_ended_at, self.first_assistant_audio_at),
            "full_turn_ms": _duration_ms(self.user_turn_ended_at, self.assistant_turn_completed_at),
        }


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
    _current_audio_chunk_count: int = 0
    _current_speech_started_at: datetime | None = None
    _pending_pingpong: LivePingPongTurn | None = None
    _recent_pingpong: deque[LivePingPongTurn] = field(default_factory=lambda: deque(maxlen=8))
    _next_turn_index: int = 1

    def note_inbound(self, message_type: str) -> None:
        now = _utcnow()
        self.inbound[message_type] += 1
        self.last_activity_at = now
        if message_type == "client.audio":
            self._current_audio_chunk_count += 1
            if self._current_speech_started_at is None:
                self._current_speech_started_at = now
        elif message_type == "client.audio_end":
            self._begin_pingpong_turn(now)

    def note_outbound(self, event_type: str, event: dict[str, Any] | None = None) -> None:
        now = _utcnow()
        self.outbound[event_type] += 1
        self.last_activity_at = now
        self._update_pingpong_turn(event_type, event or {}, now)

    def close(self) -> None:
        self.closed_at = _utcnow()
        self.last_activity_at = self.closed_at
        if self._pending_pingpong is not None:
            if self._pending_pingpong.first_assistant_event_at is None:
                self._pending_pingpong.status = "closed_without_response"
            else:
                self._pending_pingpong.status = "closed_before_completion"
            self._archive_pending_pingpong()

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
            "pingpong": self._pingpong_snapshot(),
        }

    def _begin_pingpong_turn(self, now: datetime) -> None:
        if self._pending_pingpong is not None:
            if self._pending_pingpong.first_assistant_event_at is None:
                self._pending_pingpong.status = "superseded_without_response"
            else:
                self._pending_pingpong.status = "superseded_before_completion"
            self._archive_pending_pingpong()
        self._pending_pingpong = LivePingPongTurn(
            turn_index=self._next_turn_index,
            speech_started_at=self._current_speech_started_at,
            user_turn_ended_at=now,
            audio_chunk_count=self._current_audio_chunk_count,
        )
        self._next_turn_index += 1
        self._current_audio_chunk_count = 0
        self._current_speech_started_at = None

    def _archive_pending_pingpong(self) -> None:
        if self._pending_pingpong is None:
            return
        self._recent_pingpong.appendleft(self._pending_pingpong)
        self._pending_pingpong = None

    def _update_pingpong_turn(self, event_type: str, event: dict[str, Any], now: datetime) -> None:
        turn = self._pending_pingpong
        if turn is None:
            return
        if event_type == "server.transcript" and str(event.get("role", "")).strip() == "user":
            text = str(event.get("text", "")).strip()
            if text:
                if bool(event.get("partial")):
                    turn.user_transcript_partial = text
                else:
                    turn.user_transcript_final = text
            return

        if event_type == "server.transcript" and str(event.get("role", "")).strip() != "assistant":
            return
        if event_type not in {"server.transcript", "server.audio", "server.text"}:
            return

        if turn.first_assistant_event_at is None:
            turn.first_assistant_event_at = now
        if event_type == "server.transcript" and turn.first_assistant_transcript_at is None:
            turn.first_assistant_transcript_at = now
        if event_type == "server.audio" and turn.first_assistant_audio_at is None:
            turn.first_assistant_audio_at = now
        if event_type == "server.text" and turn.first_assistant_text_at is None:
            turn.first_assistant_text_at = now

        turn_id = str(event.get("turn_id", "")).strip()
        if turn_id and turn.assistant_turn_id is None:
            turn.assistant_turn_id = turn_id

        if bool(event.get("turn_complete")):
            turn.assistant_turn_completed_at = now
            turn.status = "completed"
            self._archive_pending_pingpong()

    def _pingpong_snapshot(self) -> dict[str, Any]:
        turns = list(self._recent_pingpong)
        if self._pending_pingpong is not None:
            turns = [self._pending_pingpong, *turns]

        first_response_values = [
            value
            for value in (
                _duration_ms(turn.user_turn_ended_at, turn.first_assistant_event_at)
                for turn in turns
            )
            if value is not None
        ]
        first_audio_values = [
            value
            for value in (
                _duration_ms(turn.user_turn_ended_at, turn.first_assistant_audio_at)
                for turn in turns
            )
            if value is not None
        ]
        full_turn_values = [
            value
            for value in (
                _duration_ms(turn.user_turn_ended_at, turn.assistant_turn_completed_at)
                for turn in turns
            )
            if value is not None
        ]
        return {
            "turn_count": len(turns),
            "responded_turn_count": len(first_response_values),
            "completed_turn_count": len(full_turn_values),
            "pending_turn_count": 1 if self._pending_pingpong is not None else 0,
            "average_first_response_ms": round(mean(first_response_values), 1) if first_response_values else None,
            "average_first_audio_ms": round(mean(first_audio_values), 1) if first_audio_values else None,
            "average_full_turn_ms": round(mean(full_turn_values), 1) if full_turn_values else None,
            "recent_turns": [turn.snapshot() for turn in turns],
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

    def note_outbound(self, session_id: str, event_type: str, event: dict[str, Any] | None = None) -> None:
        with self._lock:
            record = self._active.get(session_id)
            if record is not None:
                record.note_outbound(event_type, event)

    def end_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._active.pop(session_id, None)
            if record is None:
                return None
            record.close()
            self._recent.appendleft(record)
            return record.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            active = [record.snapshot() for record in self._active.values()]
            recent = [record.snapshot() for record in self._recent]
        return {
            "active_session_count": len(active),
            "active_sessions": active,
            "recent_sessions": recent,
        }
