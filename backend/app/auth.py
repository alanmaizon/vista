"""Firebase authentication utilities.

This module initialises the Firebase Admin SDK and exposes a dependency
for verifying incoming Firebase ID tokens.  The verification uses the
application default credentials or a provided service account JSON file.
"""

import os
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Header, HTTPException, Depends

_firebase_app: Optional[firebase_admin.App] = None


def init_firebase() -> None:
    """Initialise Firebase Admin SDK if not already initialised.

    The function checks for a `FIREBASE_SERVICE_ACCOUNT_JSON` environment
    variable; if present, it uses that file to initialise the app.  If
    not provided, it falls back to the application default credentials
    (ADC), which are appropriate when running on Cloud Run with a
    service account that has the IAM role `roles/firebase.admin`.
    """
    global _firebase_app
    if _firebase_app:
        return
    # Determine the credentials source
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_path:
        cred = credentials.Certificate(service_account_path)
        _firebase_app = firebase_admin.initialize_app(cred)
    else:
        # Use application default credentials
        _firebase_app = firebase_admin.initialize_app()


async def get_current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency that validates a Firebase ID token.

    The client must send an `Authorization` header with a Bearer token.
    If the token is missing or invalid, a 401 error is raised.  On
    success, the decoded token is returned as a dictionary containing
    claims such as `uid` and `email`.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")