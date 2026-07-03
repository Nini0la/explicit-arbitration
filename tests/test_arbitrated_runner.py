from __future__ import annotations

import importlib


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _stub_model_call(_: str) -> str:
    return (
        '{"score": 61, "breakdown": {"deal_points": 20, '
        '"price_points": 21, "turn_points": 20}, "explanation": "stub"}'
    )


def _run_demo_with_stub() -> dict[str, object]:
    module = importlib.import_module("explicit_arbitration.arbitrated_runner")
    return module.run_demo_with_model_call(
        model_call=_stub_model_call,
        model_mode={"mode": "injected_test_double"},
    )


def test_run_demo_includes_transparency_sections() -> None:
    artifact = _run_demo_with_stub()

    assert "session_turns" in artifact
    assert "arbitration_trace_summary" in artifact
    assert "arbitration_trace_entries" in artifact

    assert isinstance(artifact["session_turns"], list)
    assert isinstance(artifact["arbitration_trace_summary"], dict)
    assert isinstance(artifact["arbitration_trace_entries"], list)


def test_trace_summary_matches_entry_count() -> None:
    artifact = _run_demo_with_stub()

    assert artifact["trace_entry_count"] == len(artifact["arbitration_trace_entries"])

    trace_summary = artifact["arbitration_trace_summary"]
    assert trace_summary["reason_tree_node_count"] >= 1
    assert len(trace_summary["reason_tree_node_sequence"]) >= 1
    assert trace_summary["hydra_pass_count"] >= 1


def test_trace_entries_include_pass_prompt_and_output() -> None:
    artifact = _run_demo_with_stub()
    entries = artifact["arbitration_trace_entries"]

    hydra_pass_entries = [
        entry
        for entry in entries
        if _field(entry, "component") == "hydradecide"
        and _field(entry, "step") == "hydra_pass"
    ]
    assert len(hydra_pass_entries) >= 1

    for entry in hydra_pass_entries:
        input_payload = _field(entry, "input_payload")
        output_payload = _field(entry, "output_payload")
        assert "prompt" in input_payload
        assert isinstance(input_payload["prompt"], str)
        assert "pass_output" in output_payload


def test_run_demo_uses_injected_test_double_for_deterministic_tests() -> None:
    artifact = _run_demo_with_stub()

    assert "model_mode" in artifact
    assert artifact["model_mode"]["mode"] == "injected_test_double"


def test_run_demo_requires_live_model_configuration(
    monkeypatch,
) -> None:
    module = importlib.import_module("explicit_arbitration.arbitrated_runner")
    monkeypatch.delenv("ARBITRATION_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        module.run_demo()
    except ValueError as exc:
        assert "API key is required" in str(exc)
        return
    raise AssertionError("run_demo should require live model configuration")
