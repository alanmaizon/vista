#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

python3 -m compileall "$ROOT_DIR/backend/app" "$ROOT_DIR/backend/tests"
python3 -m pytest "$ROOT_DIR/backend/tests" -q
npm --prefix "$ROOT_DIR/frontend" run build

