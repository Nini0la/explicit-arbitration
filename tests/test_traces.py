from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(slots=True)
class NegotiationTurn:
    turn_index: int
    speaker: str
    message: str
    offer_price: float | None


@dataclass(slots=True)
class NegotiationSession:
    session_id: str
    item_name: str
    reference_price: float
    turns: list[NegotiationTurn]
    outcome: str
    final_price: float | None


@dataclass(slots=True)
class TaskInput:
    task_id: str
    instruction: str
    session: NegotiationSession
    require_explanation: bool = False


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _load_run_arbitrated():
    module = importlib.import_module("explicit_arbitration.orchestrator")
    return module.run_arbitrated


def _load_trace_helpers():
    module = importlib.import_module("explicit_arbitration.traces")
    return module.new_trace_entry, module.record_trace


def _build_task() -> TaskInput:
    session = NegotiationSession(
        session_id="trace-session",
        item_name="coffee machine",
        reference_price=180.0,
        turns=[
            NegotiationTurn(0, "buyer", "Could you do 150?", 150.0),
            NegotiationTurn(1, "seller", "I can do 165.", 165.0),
        ],
        outcome="deal",
        final_price=165.0,
    )
    return TaskInput(
        task_id="task-traces",
        instruction="Compute score and emit traces.",
        session=session,
        require_explanation=True,
    )


def _stub_model_call(_: str) -> str:
    return (
        '{"score": 65, "breakdown": {"deal_points": 20, '
        '"price_points": 25, "turn_points": 20}, "explanation": "stub"}'
    )


def test_arbitrated_trace_bundle_is_non_empty() -> None:
    run_arbitrated = _load_run_arbitrated()
    task = _build_task()

    _, trace_bundle = run_arbitrated(task, _stub_model_call)
    assert isinstance(trace_bundle, list)
    assert len(trace_bundle) >= 1


def test_trace_entry_includes_required_fields() -> None:
    new_trace_entry, record_trace = _load_trace_helpers()
    store: list[object] = []

    entry = new_trace_entry(
        run_id="run-1",
        component="orchestrator",
        step="unit-test-step",
        input_payload={"a": 1},
        output_payload={"b": 2},
        metadata={"test": True},
    )
    record_trace(store, entry)
    assert len(store) == 1

    saved = store[0]
    assert _field(saved, "run_id") == "run-1"
    assert _field(saved, "component") == "orchestrator"
    assert _field(saved, "step") == "unit-test-step"
    assert _field(saved, "timestamp_utc")


def test_trace_includes_major_components_and_steps() -> None:
    run_arbitrated = _load_run_arbitrated()
    task = _build_task()

    _, trace_bundle = run_arbitrated(task, _stub_model_call)
    components = {_field(entry, "component") for entry in trace_bundle}

    assert "reasontree" in components
    assert "hydradecide" in components
    assert "orchestrator" in components


def test_hydra_passes_emit_trace_entries() -> None:
    run_arbitrated = _load_run_arbitrated()
    task = _build_task()

    _, trace_bundle = run_arbitrated(task, _stub_model_call)
    hydra_entries = [
        entry for entry in trace_bundle if _field(entry, "component") == "hydradecide"
    ]
    assert len(hydra_entries) >= 2


def test_single_run_uses_single_run_id_across_entries() -> None:
    run_arbitrated = _load_run_arbitrated()
    task = _build_task()

    _, trace_bundle = run_arbitrated(task, _stub_model_call)
    run_ids = {_field(entry, "run_id") for entry in trace_bundle}

    assert len(run_ids) == 1
