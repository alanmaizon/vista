from __future__ import annotations

import pytest

from app import db as db_module


class FakeConnection:
    def __init__(self, results: dict[str, object] | None = None) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.results = results or {}

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args) -> bool:
        return False

    async def run_sync(self, callable_obj) -> None:  # pragma: no cover - retained for interface parity
        del callable_obj

    async def execute(self, statement, params=None) -> None:
        rendered = str(statement)
        self.executed.append((rendered, params or {}))
        for pattern, value in self.results.items():
            if pattern in rendered:
                return FakeResult(value)
        return FakeResult(None)


class FakeResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar(self) -> object:
        return self.value

    def scalar_one_or_none(self) -> object:
        return self.value


class FakeEngine:
    def __init__(self, results: dict[str, object] | None = None) -> None:
        self.connection = FakeConnection(results)

    def begin(self) -> FakeConnection:
        return self.connection


@pytest.mark.asyncio
async def test_init_db_requires_applied_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_engine = FakeEngine(
        {
            "SELECT 1": 1,
            "SELECT EXISTS": True,
            "SELECT version_num FROM alembic_version": "20260314_0001",
        }
    )
    monkeypatch.setattr(db_module, "engine", fake_engine)

    await db_module.init_db()

    assert len(fake_engine.connection.executed) == 3
    assert "SELECT 1" in fake_engine.connection.executed[0][0]
    assert "SELECT EXISTS" in fake_engine.connection.executed[1][0]
    assert "SELECT version_num FROM alembic_version" in fake_engine.connection.executed[2][0]


@pytest.mark.asyncio
async def test_init_db_raises_when_migrations_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_engine = FakeEngine(
        {
            "SELECT 1": 1,
            "SELECT EXISTS": False,
        }
    )
    monkeypatch.setattr(db_module, "engine", fake_engine)

    with pytest.raises(RuntimeError, match="alembic -c backend/alembic.ini upgrade head"):
        await db_module.init_db()
