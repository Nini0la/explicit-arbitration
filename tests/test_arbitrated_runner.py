from __future__ import annotations

import importlib


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def test_run_demo_includes_transparency_sections() -> None:
    module = importlib.import_module("explicit_arbitration.arbitrated_runner")
    artifact = module.run_demo()

    assert "session_turns" in artifact
    assert "arbitration_trace_summary" in artifact
    assert "arbitration_trace_entries" in artifact

    assert isinstance(artifact["session_turns"], list)
    assert isinstance(artifact["arbitration_trace_summary"], dict)
    assert isinstance(artifact["arbitration_trace_entries"], list)


def test_trace_summary_matches_entry_count() -> None:
    module = importlib.import_module("explicit_arbitration.arbitrated_runner")
    artifact = module.run_demo()

    assert artifact["trace_entry_count"] == len(artifact["arbitration_trace_entries"])

    trace_summary = artifact["arbitration_trace_summary"]
    assert trace_summary["reason_tree_node_count"] >= 1
    assert len(trace_summary["reason_tree_node_sequence"]) >= 1
    assert trace_summary["hydra_pass_count"] >= 1


def test_trace_entries_include_pass_prompt_and_output() -> None:
    module = importlib.import_module("explicit_arbitration.arbitrated_runner")
    artifact = module.run_demo()
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
