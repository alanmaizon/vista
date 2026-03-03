from __future__ import annotations

import pytest

from app import db as db_module
from app.domains.base import DEFAULT_DOMAIN


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.run_sync_calls: list[object] = []

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args) -> bool:
        return False

    async def run_sync(self, callable_obj) -> None:  # pragma: no cover - invoked for side effect tracking
        self.run_sync_calls.append(callable_obj)

    async def execute(self, statement, params=None) -> None:
        self.executed.append((str(statement), params or {}))


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def begin(self) -> FakeConnection:
        return self.connection


@pytest.mark.asyncio
async def test_init_db_sets_domain_default(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_engine = FakeEngine()
    monkeypatch.setattr(db_module, "engine", fake_engine)

    await db_module.init_db()

    assert len(fake_engine.connection.run_sync_calls) == 1
    assert len(fake_engine.connection.executed) == 2

    add_stmt, add_params = fake_engine.connection.executed[0]
    alter_stmt, alter_params = fake_engine.connection.executed[1]

    assert "ADD COLUMN IF NOT EXISTS domain" in add_stmt
    assert add_params.get("default_domain") == DEFAULT_DOMAIN
    assert "ALTER COLUMN domain SET DEFAULT" in alter_stmt
    assert alter_params.get("default_domain") == DEFAULT_DOMAIN
