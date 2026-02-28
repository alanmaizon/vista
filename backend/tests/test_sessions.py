from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi import HTTPException

from app import sessions as sessions_api
from app.models import Session
from app.schemas import SessionCreate, SessionUpdate


def build_session(
    *,
    session_id: uuid.UUID | None = None,
    user_id: str = "user-123",
    mode: str = "NAV_FIND",
) -> Session:
    session = Session(
        id=session_id or uuid.uuid4(),
        user_id=user_id,
        mode=mode,
        risk_mode="NORMAL",
        goal="Find the exit sign",
        summary=None,
        success=None,
        model_id=None,
        region=None,
    )
    session.started_at = datetime.now(timezone.utc)
    session.ended_at = None
    return session


class FakeScalarList:
    def __init__(self, values: list[Session]) -> None:
        self._values = values

    def all(self) -> list[Session]:
        return self._values


class FakeResult:
    def __init__(
        self,
        *,
        scalar: Session | None = None,
        values: list[Session] | None = None,
    ) -> None:
        self._scalar = scalar
        self._values = values or []

    def scalar_one_or_none(self) -> Session | None:
        return self._scalar

    def scalars(self) -> FakeScalarList:
        return FakeScalarList(self._values)


class FakeExecuteDB:
    def __init__(self, result: FakeResult | None = None) -> None:
        self.result = result or FakeResult()
        self.executed = []
        self.commit_calls = 0
        self.refresh_calls = 0

    async def execute(self, statement) -> FakeResult:
        self.executed.append(statement)
        return self.result

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, _instance: Session) -> None:
        self.refresh_calls += 1


class FakeCreateDB(FakeExecuteDB):
    def __init__(self) -> None:
        super().__init__()
        self.added: Session | None = None

    def add(self, instance: Session) -> None:
        self.added = instance

    async def refresh(self, instance: Session) -> None:
        await super().refresh(instance)
        if instance.id is None:
            instance.id = uuid.uuid4()
        if instance.started_at is None:
            instance.started_at = datetime.now(timezone.utc)
        instance.ended_at = None
        instance.summary = None
        instance.success = None
        instance.model_id = None
        instance.region = None


@pytest.mark.asyncio
async def test_create_session_sets_owner_and_defaults() -> None:
    db = FakeCreateDB()

    result = await sessions_api.create_session(
        payload=SessionCreate(mode="READ_TEXT", goal="Read the menu"),
        current_user={"uid": "firebase-user"},
        db=db,
    )

    assert db.added is not None
    assert db.commit_calls == 1
    assert result.user_id == "firebase-user"
    assert result.mode == "READ_TEXT"
    assert result.risk_mode == "NORMAL"
    assert result.goal == "Read the menu"
    assert result.ended_at is None


@pytest.mark.asyncio
async def test_list_sessions_serializes_owned_sessions() -> None:
    sessions = [
        build_session(mode="NAV_FIND"),
        build_session(mode="SHOP_VERIFY"),
    ]
    db = FakeExecuteDB(FakeResult(values=sessions))

    result = await sessions_api.list_sessions(
        current_user={"uid": "firebase-user"},
        db=db,
    )

    assert [item.mode for item in result] == ["NAV_FIND", "SHOP_VERIFY"]
    assert len(db.executed) == 1


@pytest.mark.asyncio
async def test_get_owned_session_raises_not_found() -> None:
    db = FakeExecuteDB(FakeResult(scalar=None))

    with pytest.raises(HTTPException) as exc_info:
        await sessions_api._get_owned_session(db, uuid.uuid4(), "firebase-user")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_owned_session_raises_forbidden_for_wrong_user() -> None:
    db = FakeExecuteDB(FakeResult(scalar=build_session(user_id="another-user")))

    with pytest.raises(HTTPException) as exc_info:
        await sessions_api._get_owned_session(db, uuid.uuid4(), "firebase-user")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_update_session_sets_ended_at_when_ended_true(monkeypatch: pytest.MonkeyPatch) -> None:
    session = build_session()
    db = FakeExecuteDB()

    async def fake_get_owned_session(*_args, **_kwargs) -> Session:
        return session

    monkeypatch.setattr(sessions_api, "_get_owned_session", fake_get_owned_session)

    before = datetime.now(timezone.utc)
    result = await sessions_api.update_session(
        session_id=session.id,
        payload=SessionUpdate(ended=True, success=True, risk_mode="CAUTION"),
        current_user={"uid": session.user_id},
        db=db,
    )

    assert db.commit_calls == 1
    assert db.refresh_calls == 1
    assert session.ended_at is not None
    assert session.ended_at >= before
    assert result.success is True
    assert result.risk_mode == "CAUTION"


@pytest.mark.asyncio
async def test_delete_session_returns_204(monkeypatch: pytest.MonkeyPatch) -> None:
    session = build_session()
    db = FakeExecuteDB()

    async def fake_get_owned_session(*_args, **_kwargs) -> Session:
        return session

    monkeypatch.setattr(sessions_api, "_get_owned_session", fake_get_owned_session)

    response = await sessions_api.delete_session(
        session_id=session.id,
        current_user={"uid": session.user_id},
        db=db,
    )

    assert response.status_code == 204
    assert db.commit_calls == 1
    assert len(db.executed) == 1
