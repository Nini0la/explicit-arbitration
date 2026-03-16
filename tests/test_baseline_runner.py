from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest


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


def _load_baseline_module():
    return importlib.import_module("explicit_arbitration.baseline_runner")


@pytest.fixture()
def sample_task() -> TaskInput:
    session = NegotiationSession(
        session_id="baseline-session",
        item_name="tablet",
        reference_price=400.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 320?", 320.0),
            NegotiationTurn(1, "seller", "I can do 350.", 350.0),
            NegotiationTurn(2, "buyer", "Deal at 340.", 340.0),
        ],
        outcome="deal",
        final_price=340.0,
    )
    return TaskInput(
        task_id="task-baseline",
        instruction="Compute the negotiation score directly.",
        session=session,
        require_explanation=True,
    )


def _stub_model_call(_: str) -> str:
    return (
        '{"score": 59, "breakdown": {"deal_points": 20, '
        '"price_points": 19, "turn_points": 20}, "explanation": "baseline-stub"}'
    )


def test_run_baseline_accepts_same_task_input_as_arbitrated(
    sample_task: TaskInput,
) -> None:
    module = _load_baseline_module()
    run_baseline = module.run_baseline

    result = run_baseline(sample_task, _stub_model_call)
    assert _field(result, "score") is not None


def test_run_baseline_returns_parseable_score_result(sample_task: TaskInput) -> None:
    module = _load_baseline_module()
    run_baseline = module.run_baseline

    result = run_baseline(sample_task, _stub_model_call)
    score = _field(result, "score")
    breakdown = _field(result, "breakdown")

    assert isinstance(score, int)
    assert isinstance(breakdown, dict)
    assert {"deal_points", "price_points", "turn_points"} <= set(breakdown.keys())


def test_run_baseline_does_not_call_reasontree_or_hydra(
    monkeypatch: pytest.MonkeyPatch,
    sample_task: TaskInput,
) -> None:
    baseline_module = _load_baseline_module()
    run_baseline = baseline_module.run_baseline

    def _fail(*args, **kwargs):
        del args, kwargs
        raise AssertionError("Baseline must not call ReasonTree/HydraDecide internals.")

    monkeypatch.setattr(baseline_module, "build_reason_tree", _fail, raising=False)
    monkeypatch.setattr(baseline_module, "run_hydra_for_node", _fail, raising=False)

    try:
        reasontree_module = importlib.import_module("explicit_arbitration.reasontree")
        monkeypatch.setattr(
            reasontree_module,
            "build_reason_tree",
            _fail,
            raising=False,
        )
    except ModuleNotFoundError:
        pass

    try:
        hydra_module = importlib.import_module("explicit_arbitration.hydradecide")
        monkeypatch.setattr(hydra_module, "run_hydra_for_node", _fail, raising=False)
    except ModuleNotFoundError:
        pass

    result = run_baseline(sample_task, _stub_model_call)
    assert _field(result, "score") is not None
