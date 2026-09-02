from src.chimera_defensive_simulator import build_defensive_timeline, summarize_timeline


def test_timeline_has_only_safe_actions():
    steps = build_defensive_timeline()
    joined = " ".join(step.safe_action.lower() for step in steps)
    forbidden = ["password", "remote shell", "hide traces", "system change"]
    assert all(term not in joined for term in forbidden)


def test_summary_is_serializable_shape():
    summary = summarize_timeline(build_defensive_timeline())
    assert isinstance(summary, list)
    assert summary
    expected = {"phase", "objective", "severity", "safe_action", "evidence_to_collect"}
    assert expected.issubset(summary[0])
