from __future__ import annotations

from app.eval_live_pingpong import run_eval


def test_live_pingpong_eval_produces_grading_report() -> None:
    report = run_eval()

    assert report["scenario_count"] == 2
    assert report["aggregate_score"] >= 0.85
    assert report["pass"] is True
    assert report["rubric"]["turn_completion"] == 1.0
    assert report["rubric"]["first_response_latency"] > 0.0
    assert report["scenarios"][0]["turn"]["status"] == "completed"
    assert report["scenarios"][0]["turn"]["first_response_ms"] is not None
