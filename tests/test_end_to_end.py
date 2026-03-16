from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass, is_dataclass

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


def _normalize(value: object):
    if is_dataclass(value):
        return {k: _normalize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if hasattr(value, "__dict__"):
        return {
            key: _normalize(val)
            for key, val in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _load_symbol(module_path: str, symbol: str):
    module = importlib.import_module(module_path)
    return getattr(module, symbol)


def _build_demo_task() -> TaskInput:
    session = NegotiationSession(
        session_id="demo-session-1",
        item_name="mechanical keyboard",
        reference_price=150.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 120?", 120.0),
            NegotiationTurn(1, "seller", "I can do 135.", 135.0),
            NegotiationTurn(2, "buyer", "Deal at 130.", 130.0),
        ],
        outcome="deal",
        final_price=130.0,
    )
    return TaskInput(
        task_id="task-demo-e2e",
        instruction="Score this negotiation session.",
        session=session,
        require_explanation=True,
    )


def _stub_model_call(_: str) -> str:
    return (
        '{"score": 61, "breakdown": {"deal_points": 20, '
        '"price_points": 21, "turn_points": 20}, "explanation": "stub"}'
    )


def _extract_sample_sessions(sample_sessions_module) -> list[object]:
    if hasattr(sample_sessions_module, "get_sample_sessions"):
        sessions = sample_sessions_module.get_sample_sessions()
    elif hasattr(sample_sessions_module, "SAMPLE_SESSIONS"):
        sessions = sample_sessions_module.SAMPLE_SESSIONS
    elif hasattr(sample_sessions_module, "sample_sessions"):
        sessions = sample_sessions_module.sample_sessions
    else:
        pytest.fail(
            "sample_sessions must expose get_sample_sessions() or SAMPLE_SESSIONS."
        )

    assert isinstance(sessions, (list, tuple))
    return list(sessions)


def _find_expected_scores(sample_sessions_module):
    candidate_names = [
        "EXPECTED_GROUND_TRUTH",
        "EXPECTED_SCORES",
        "EXPECTED_RESULTS",
        "SAMPLE_EXPECTED_SCORES",
    ]
    for name in candidate_names:
        if hasattr(sample_sessions_module, name):
            return getattr(sample_sessions_module, name)
    return None


def test_demo_session_runs_ground_truth_baseline_and_arbitrated() -> None:
    compute_ground_truth_score = _load_symbol(
        "explicit_arbitration.scoring_rules",
        "compute_ground_truth_score",
    )
    run_baseline = _load_symbol("explicit_arbitration.baseline_runner", "run_baseline")
    run_arbitrated = _load_symbol("explicit_arbitration.orchestrator", "run_arbitrated")

    task = _build_demo_task()
    ground_truth = compute_ground_truth_score(task.session)
    baseline = run_baseline(task, _stub_model_call)
    arbitrated, trace_bundle = run_arbitrated(task, _stub_model_call)

    assert isinstance(_field(ground_truth, "score"), int)
    assert isinstance(_field(baseline, "score"), int)
    assert isinstance(_field(arbitrated, "score"), int)
    assert isinstance(trace_bundle, list)
    assert len(trace_bundle) >= 1


def test_demo_produces_comparison_artifact() -> None:
    compute_ground_truth_score = _load_symbol(
        "explicit_arbitration.scoring_rules",
        "compute_ground_truth_score",
    )
    run_baseline = _load_symbol("explicit_arbitration.baseline_runner", "run_baseline")
    run_arbitrated = _load_symbol("explicit_arbitration.orchestrator", "run_arbitrated")

    task = _build_demo_task()
    ground_truth = compute_ground_truth_score(task.session)
    baseline = run_baseline(task, _stub_model_call)
    arbitrated, trace_bundle = run_arbitrated(task, _stub_model_call)

    artifact = {
        "session_id": task.session.session_id,
        "ground_truth_score": _field(ground_truth, "score"),
        "baseline_score": _field(baseline, "score"),
        "arbitrated_score": _field(arbitrated, "score"),
        "baseline_match": _field(baseline, "score") == _field(ground_truth, "score"),
        "arbitrated_match": _field(arbitrated, "score")
        == _field(ground_truth, "score"),
        "trace_entry_count": len(trace_bundle),
    }

    encoded = json.dumps(artifact, sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded["session_id"] == task.session.session_id
    assert "ground_truth_score" in decoded
    assert "baseline_score" in decoded
    assert "arbitrated_score" in decoded
    assert "baseline_match" in decoded
    assert "arbitrated_match" in decoded
    assert decoded["trace_entry_count"] >= 1


def test_sample_sessions_minimum_count_and_determinism() -> None:
    sample_sessions_module = importlib.import_module(
        "explicit_arbitration.sample_sessions"
    )
    sessions_first = _extract_sample_sessions(sample_sessions_module)
    sessions_second = _extract_sample_sessions(sample_sessions_module)

    assert len(sessions_first) >= 2
    assert _normalize(sessions_first) == _normalize(sessions_second)

    expected_lookup = _find_expected_scores(sample_sessions_module)
    for session in sessions_first:
        session_id = _field(session, "session_id")
        has_embedded_expected = any(
            hasattr(session, attr)
            for attr in (
                "expected_ground_truth_score",
                "expected_score",
                "ground_truth_score",
            )
        ) or (
            isinstance(session, dict)
            and any(
                key in session
                for key in (
                    "expected_ground_truth_score",
                    "expected_score",
                    "ground_truth_score",
                )
            )
        )

        has_lookup_expected = isinstance(expected_lookup, dict) and (
            session_id in expected_lookup
        )

        assert has_embedded_expected or has_lookup_expected


def test_sample_sessions_support_plausible_divergence_scenarios() -> None:
    sample_sessions_module = importlib.import_module(
        "explicit_arbitration.sample_sessions"
    )
    sessions = _extract_sample_sessions(sample_sessions_module)

    outcomes = {_field(session, "outcome") for session in sessions}
    turn_counts = {len(_field(session, "turns")) for session in sessions}

    assert "deal" in outcomes
    assert "no_deal" in outcomes
    assert len(turn_counts) >= 2
