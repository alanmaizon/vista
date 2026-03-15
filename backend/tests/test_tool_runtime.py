from backend.app.agents.tools.runtime import ToolExecutionError, execute_tool_call


def test_parse_tool_returns_analysis() -> None:
    result = execute_tool_call(
        "parse_passage",
        {
            "text": "logos gar didaskalos",
            "focus_word": "logos",
        },
    )
    assert result["tool"] == "parse_passage"
    assert result["status"] == "ok"
    assert result["analysis"]["part_of_speech"] in {"noun_or_adjective", "verb", "unknown"}


def test_grade_tool_scores_against_reference() -> None:
    result = execute_tool_call(
        "grade_attempt",
        {
            "learner_answer": "the word became flesh",
            "reference_answer": "the word became flesh",
        },
    )
    assert result["tool"] == "grade_attempt"
    assert result["status"] == "ok"
    assert result["score"] >= 90
    assert result["band"] in {"excellent", "good"}


def test_drill_tool_generates_drill() -> None:
    result = execute_tool_call(
        "generate_drill",
        {
            "mistake_summary": "Learner confused the case ending on the subject noun.",
            "mode": "morphology_coach",
            "focus_word": "logos",
        },
    )
    assert result["tool"] == "generate_drill"
    assert result["status"] == "ok"
    assert result["drill_type"] == "morphology_repair"
    assert len(result["drill"]["steps"]) == 3


def test_unknown_tool_raises_execution_error() -> None:
    try:
        execute_tool_call("unknown_tool", {})
    except ToolExecutionError:
        return
    raise AssertionError("Expected ToolExecutionError for unknown tool")

