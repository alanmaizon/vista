#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR/backend"

python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

