"""Firebase authentication utilities."""

import asyncio
import json
import os
from typing import Any, Optional

import firebase_admin
from fastapi import Header, HTTPException
from firebase_admin import auth, credentials

_firebase_app: Optional[firebase_admin.App] = None


def _load_firebase_credentials() -> Optional[credentials.Base]:
    """Load Firebase credentials from env, supporting JSON content or a file path."""
    raw_value = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("{"):
        return credentials.Certificate(json.loads(raw_value))
    return credentials.Certificate(raw_value)


def init_firebase() -> None:
    """Initialise Firebase Admin SDK once per process."""
    global _firebase_app
    if _firebase_app:
        return
    cred = _load_firebase_credentials()
    if cred is None:
        _firebase_app = firebase_admin.initialize_app()
        return
    _firebase_app = firebase_admin.initialize_app(cred)


def verify_firebase_token(token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return the decoded claims."""
    init_firebase()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Firebase token")
    try:
        return auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase token") from exc


async def get_current_user(authorization: str = Header(default="")) -> dict[str, Any]:
    """FastAPI dependency that validates a Bearer token from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return await asyncio.to_thread(verify_firebase_token, token)
