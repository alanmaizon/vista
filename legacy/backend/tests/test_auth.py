from __future__ import annotations

import types

import pytest
from fastapi import HTTPException

from app import auth as auth_module


@pytest.fixture(autouse=True)
def reset_firebase_app_state(monkeypatch):
    monkeypatch.setattr(auth_module, "_firebase_app", None)


def test_init_firebase_passes_resolved_project_id_from_service_account(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        '{"project_id":"vista-ai-488623","client_email":"firebase-adminsdk@vista-ai-488623.iam.gserviceaccount.com"}',
    )
    monkeypatch.setattr(auth_module.settings, "firebase_web_config", "")
    monkeypatch.setattr(auth_module.settings, "project_id", "")
    monkeypatch.setattr(auth_module.credentials, "Certificate", lambda payload: {"payload": payload})

    def fake_initialize_app(cred=None, options=None):
        captured["cred"] = cred
        captured["options"] = options
        return types.SimpleNamespace(name="firebase-app")

    monkeypatch.setattr(auth_module.firebase_admin, "initialize_app", fake_initialize_app)

    auth_module.init_firebase()

    assert captured["options"] == {"projectId": "vista-ai-488623"}
    assert captured["cred"] == {
        "payload": {
            "project_id": "vista-ai-488623",
            "client_email": "firebase-adminsdk@vista-ai-488623.iam.gserviceaccount.com",
        }
    }


def test_init_firebase_warns_on_project_mismatch(monkeypatch, caplog) -> None:
    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        '{"project_id":"vista-ai-488623","client_email":"firebase-adminsdk@vista-ai-488623.iam.gserviceaccount.com"}',
    )
    monkeypatch.setattr(
        auth_module.settings,
        "firebase_web_config",
        '{"apiKey":"test","projectId":"different-project"}',
    )
    monkeypatch.setattr(auth_module.settings, "project_id", "")
    monkeypatch.setattr(auth_module.credentials, "Certificate", lambda payload: {"payload": payload})
    monkeypatch.setattr(
        auth_module.firebase_admin,
        "initialize_app",
        lambda cred=None, options=None: types.SimpleNamespace(name="firebase-app"),
    )

    with caplog.at_level("WARNING"):
        auth_module.init_firebase()

    assert "Firebase project mismatch" in caplog.text


def test_create_firebase_session_cookie_logs_and_raises_backend_error(monkeypatch, caplog) -> None:
    monkeypatch.setattr(auth_module, "init_firebase", lambda: None)

    def fail_create_session_cookie(*_args, **_kwargs):
        raise RuntimeError("firebase auth unavailable")

    monkeypatch.setattr(auth_module.auth, "create_session_cookie", fail_create_session_cookie)

    with caplog.at_level("ERROR"), pytest.raises(HTTPException) as exc_info:
        auth_module.create_firebase_session_cookie("test-id-token")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Firebase session cookie creation failed on the backend"
    assert "Firebase session cookie creation failed" in caplog.text
