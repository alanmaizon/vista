"""Firebase authentication utilities."""

import asyncio
import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import firebase_admin
from fastapi import Header, HTTPException, Request as FastAPIRequest
from firebase_admin import auth, credentials

from .settings import settings

_firebase_app: Optional[firebase_admin.App] = None
logger = logging.getLogger("eurydice.auth")


def _load_json_object(raw_value: str, *, label: str) -> dict[str, Any]:
    """Load a JSON object from raw content or a file path."""
    if raw_value.startswith("{"):
        raw_json = raw_value
    else:
        try:
            raw_json = Path(raw_value).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"{label} file could not be read: {raw_value}") from exc
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return parsed


def _firebase_service_account_payload() -> dict[str, Any] | None:
    """Load the Firebase Admin service account payload if configured."""
    raw_value = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw_value:
        return None
    return _load_json_object(raw_value, label="Firebase service account JSON")


def _load_firebase_credentials() -> Optional[credentials.Base]:
    """Load Firebase credentials from env, supporting JSON content or a file path."""
    payload = _firebase_service_account_payload()
    if payload is None:
        return None
    return credentials.Certificate(payload)


def _firebase_web_config_payload() -> dict[str, Any] | None:
    """Parse the Firebase web config when it is present and valid JSON."""
    raw_config = settings.firebase_web_config.strip()
    if not raw_config:
        return None
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError:
        logger.warning("VISTA_FIREBASE_WEB_CONFIG is invalid JSON")
        return None
    if not isinstance(parsed, dict):
        logger.warning("VISTA_FIREBASE_WEB_CONFIG must be a JSON object")
        return None
    return parsed


def _firebase_web_api_key() -> str:
    raw_config = settings.firebase_web_config.strip()
    if not raw_config:
        raise HTTPException(status_code=500, detail="Firebase web config is not set on the backend")
    parsed = _firebase_web_config_payload()
    if parsed is None:
        raise HTTPException(status_code=500, detail="Firebase web config JSON is invalid")
    api_key = str(parsed.get("apiKey", "")).strip() if isinstance(parsed, dict) else ""
    if not api_key:
        raise HTTPException(status_code=500, detail="Firebase web config does not contain apiKey")
    return api_key


def _resolved_firebase_project_id() -> str:
    """Resolve the Firebase project id from service account, web config, or app settings."""
    service_account_payload = _firebase_service_account_payload() or {}
    service_account_project_id = str(service_account_payload.get("project_id", "")).strip()
    web_config_payload = _firebase_web_config_payload() or {}
    web_project_id = str(web_config_payload.get("projectId", "")).strip()
    settings_project_id = settings.project_id.strip()

    if service_account_project_id and web_project_id and service_account_project_id != web_project_id:
        logger.warning(
            "Firebase project mismatch: service account project_id=%s, web config projectId=%s",
            service_account_project_id,
            web_project_id,
        )

    return service_account_project_id or web_project_id or settings_project_id


def _identity_toolkit_request(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _firebase_web_api_key()
    url = f"https://identitytoolkit.googleapis.com/v1/{endpoint}?key={api_key}"
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_message = "Authentication failed"
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            error_message = str(parsed.get("error", {}).get("message") or error_message)
        except json.JSONDecodeError:
            pass
        status_code = 401 if exc.code in {400, 401, 403} else 502
        raise HTTPException(status_code=status_code, detail=f"Authentication failed: {error_message}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Firebase authentication service") from exc

    try:
        parsed_response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Firebase authentication response was invalid JSON") from exc
    if not isinstance(parsed_response, dict):
        raise HTTPException(status_code=502, detail="Firebase authentication response was not an object")
    return parsed_response


def sign_in_with_email_password(email: str, password: str) -> str:
    payload = _identity_toolkit_request(
        "accounts:signInWithPassword",
        {
            "email": email,
            "password": password,
            "returnSecureToken": True,
        },
    )
    id_token = str(payload.get("idToken", "")).strip()
    if not id_token:
        raise HTTPException(status_code=502, detail="Firebase login succeeded but returned no idToken")
    return id_token


def sign_in_anonymously() -> str:
    payload = _identity_toolkit_request(
        "accounts:signUp",
        {
            "returnSecureToken": True,
        },
    )
    id_token = str(payload.get("idToken", "")).strip()
    if not id_token:
        raise HTTPException(status_code=502, detail="Firebase anonymous login returned no idToken")
    return id_token


def init_firebase() -> None:
    """Initialise Firebase Admin SDK once per process."""
    global _firebase_app
    if _firebase_app:
        return
    cred = _load_firebase_credentials()
    project_id = _resolved_firebase_project_id()
    options = {"projectId": project_id} if project_id else None
    if cred is None:
        _firebase_app = firebase_admin.initialize_app(options=options) if options else firebase_admin.initialize_app()
        logger.info("Firebase Admin initialised with ADC for project_id=%s", project_id or "<unset>")
        return
    _firebase_app = firebase_admin.initialize_app(cred, options=options) if options else firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin initialised with service account for project_id=%s", project_id or "<unset>")


def verify_firebase_token(token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return the decoded claims."""
    init_firebase()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Firebase token")
    try:
        return auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase token") from exc


def create_firebase_session_cookie(id_token: str) -> str:
    """Mint a Firebase session cookie from a valid ID token."""
    init_firebase()
    try:
        return auth.create_session_cookie(
            id_token,
            expires_in=timedelta(seconds=max(300, settings.session_cookie_max_age_seconds)),
        )
    except Exception as exc:
        logger.exception("Firebase session cookie creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Firebase session cookie creation failed on the backend") from exc


def verify_firebase_session_cookie(session_cookie: str) -> dict[str, Any]:
    """Verify and decode a Firebase session cookie."""
    init_firebase()
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Missing Firebase session cookie")
    try:
        return auth.verify_session_cookie(session_cookie, check_revoked=True)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase session cookie") from exc


async def get_current_user(
    request: FastAPIRequest,
    authorization: str = Header(default=""),
) -> dict[str, Any]:
    """Authenticate either with Bearer token or backend-issued session cookie."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        return await asyncio.to_thread(verify_firebase_token, token)

    session_cookie = request.cookies.get(settings.session_cookie_name, "").strip()
    if session_cookie:
        return await asyncio.to_thread(verify_firebase_session_cookie, session_cookie)

    raise HTTPException(status_code=401, detail="Missing authentication credentials")
