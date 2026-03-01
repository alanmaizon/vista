"""Validate the local Vista AI backend environment.

Usage:
  set -a
  source backend/.env
  set +a
  python3 backend/check_local_env.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


DEPRECATED_MODEL = "gemini-live-2.5-flash-preview-native-audio-09-2025"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def check_file_path(name: str, errors: list[str], warnings: list[str]) -> None:
    value = os.getenv(name, "").strip()
    if not value:
        warnings.append(f"{name} is not set")
        return
    if value.startswith("{"):
        return
    if not Path(value).expanduser().exists():
        errors.append(f"{name} points to a missing file: {value}")


def main() -> int:
    load_env_file(ENV_PATH)

    py_version = sys.version_info
    if py_version < (3, 11) or py_version >= (3, 14):
        print(
            "Unsupported Python version: "
            f"{py_version.major}.{py_version.minor}. "
            "Use Python 3.11, 3.12, or 3.13 for this repo."
        )
        return 1

    required = (
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
        "DB_HOST",
        "DB_PORT",
        "VISTA_MODEL_ID",
        "VISTA_LOCATION",
        "VISTA_FALLBACK_LOCATION",
        "VISTA_PROJECT_ID",
    )
    errors: list[str] = []
    warnings: list[str] = []

    for name in required:
        if not os.getenv(name, "").strip():
            errors.append(f"{name} is missing")

    if os.getenv("VISTA_MODEL_ID", "").strip() == DEPRECATED_MODEL:
        errors.append("VISTA_MODEL_ID uses the deprecated preview live model")

    if os.getenv("CLOUDSQL_INSTANCE_CONNECTION_NAME", "").strip():
        warnings.append(
            "CLOUDSQL_INSTANCE_CONNECTION_NAME is set. For local TCP testing, leave it blank and use DB_HOST/DB_PORT."
        )

    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ and not os.environ[
        "GOOGLE_APPLICATION_CREDENTIALS"
    ].strip():
        errors.append(
            "GOOGLE_APPLICATION_CREDENTIALS is explicitly set to an empty value. "
            "Remove it or comment it out to use gcloud ADC."
        )

    check_file_path("FIREBASE_SERVICE_ACCOUNT_JSON", errors, warnings)
    check_file_path("GOOGLE_APPLICATION_CREDENTIALS", errors, warnings)

    if not os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip():
        warnings.append(
            "Firebase Admin will fall back to Application Default Credentials if available."
        )
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip():
        warnings.append(
            "Vertex AI will rely on gcloud ADC. Run: gcloud auth application-default login"
        )

    print(f"Loaded env file: {ENV_PATH}")
    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"  - {item}")
    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"  - {item}")

    if errors:
        print("\nLocal environment is not ready.")
        return 1

    print("\nLocal environment looks ready.")
    print("Next:")
    print("  1. cd backend")
    print("  2. uvicorn app.main:app --reload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
