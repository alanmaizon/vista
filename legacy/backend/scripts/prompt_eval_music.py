#!/usr/bin/env python3
"""Run a lightweight prompt-quality evaluation for Eurydice music prompts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domains.music.constitution import DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS
from app.domains.music.prompt_eval import evaluate_prompt_quality


def main() -> int:
    report = evaluate_prompt_quality(DEFAULT_MUSIC_SYSTEM_INSTRUCTIONS)
    print(json.dumps(report, indent=2))
    return 0 if report["score"] >= 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

