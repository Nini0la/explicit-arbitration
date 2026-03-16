from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import SimpleNamespace

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


@dataclass(slots=True)
class ReasonTreeNode:
    node_id: str
    purpose: str
    prompt: str
    depends_on: list[str]
    expected_output_type: str


def _load_orchestrator_module():
    return importlib.import_module("explicit_arbitration.orchestrator")


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


@pytest.fixture()
def sample_task() -> TaskInput:
    session = NegotiationSession(
        session_id="orchestrator-session",
        item_name="office chair",
        reference_price=300.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 240?", 240.0),
            NegotiationTurn(1, "seller", "I can do 270.", 270.0),
            NegotiationTurn(2, "buyer", "Deal at 260?", 260.0),
        ],
        outcome="deal",
        final_price=260.0,
    )
    return TaskInput(
        task_id="task-orchestrator",
        instruction="Compute score using decomposed arbitration.",
        session=session,
        require_explanation=True,
    )


def _sample_nodes() -> list[ReasonTreeNode]:
    return [
        ReasonTreeNode(
            node_id="node-facts",
            purpose="Extract facts",
            prompt="Extract negotiation facts.",
            depends_on=[],
            expected_output_type="facts",
        ),
        ReasonTreeNode(
            node_id="node-pricing",
            purpose="Evaluate pricing",
            prompt="Evaluate pricing from extracted facts.",
            depends_on=["node-facts"],
            expected_output_type="pricing_eval",
        ),
        ReasonTreeNode(
            node_id="node-final",
            purpose="Compute final score",
            prompt="Compute final score from prior outputs.",
            depends_on=["node-facts", "node-pricing"],
            expected_output_type="final_score",
        ),
    ]


def _hydra_result(node_id: str, final_output: str) -> SimpleNamespace:
    return SimpleNamespace(
        node_id=node_id,
        pass_count=2,
        pass_outputs=["p1", "p2"],
        contradictions=[],
        revision_notes=[],
        final_output=final_output,
    )


def test_run_arbitrated_executes_nodes_in_reason_tree_order(
    monkeypatch: pytest.MonkeyPatch,
    sample_task: TaskInput,
) -> None:
    module = _load_orchestrator_module()
    run_arbitrated = module.run_arbitrated
    nodes = _sample_nodes()
    call_order: list[str] = []

    def fake_build_reason_tree(task: TaskInput):
        assert task.task_id == sample_task.task_id
        return nodes

    def fake_run_hydra_for_node(node, task, prior_node_outputs, model_call, passes=2):
        assert task.task_id == sample_task.task_id
        call_order.append(node.node_id)
        if node.node_id == "node-final":
            return _hydra_result(
                node.node_id,
                '{"score": 71, "breakdown": {"deal_points": 20, '
                '"price_points": 31, "turn_points": 20}, "explanation": "ok"}',
            )
        return _hydra_result(node.node_id, f"intermediate-{node.node_id}")

    monkeypatch.setattr(module, "build_reason_tree", fake_build_reason_tree)
    monkeypatch.setattr(module, "run_hydra_for_node", fake_run_hydra_for_node)

    run_arbitrated(sample_task, lambda _: "unused")
    assert call_order == [node.node_id for node in nodes]


def test_run_arbitrated_threads_prior_node_outputs(
    monkeypatch: pytest.MonkeyPatch,
    sample_task: TaskInput,
) -> None:
    module = _load_orchestrator_module()
    run_arbitrated = module.run_arbitrated
    nodes = _sample_nodes()
    prior_snapshots: list[dict[str, object]] = []

    def fake_build_reason_tree(_: TaskInput):
        return nodes

    def fake_run_hydra_for_node(node, task, prior_node_outputs, model_call, passes=2):
        del task, model_call, passes
        prior_snapshots.append(dict(prior_node_outputs))
        if node.node_id == "node-facts":
            return _hydra_result(node.node_id, "facts-output")
        if node.node_id == "node-pricing":
            return _hydra_result(node.node_id, "pricing-output")
        return _hydra_result(
            node.node_id,
            '{"score": 63, "breakdown": {"deal_points": 20, '
            '"price_points": 23, "turn_points": 20}, "explanation": "final"}',
        )

    monkeypatch.setattr(module, "build_reason_tree", fake_build_reason_tree)
    monkeypatch.setattr(module, "run_hydra_for_node", fake_run_hydra_for_node)

    run_arbitrated(sample_task, lambda _: "unused")

    assert prior_snapshots[0] == {}
    assert prior_snapshots[1] == {"node-facts": "facts-output"}
    assert prior_snapshots[2] == {
        "node-facts": "facts-output",
        "node-pricing": "pricing-output",
    }


def test_run_arbitrated_returns_score_result_and_trace_bundle(
    monkeypatch: pytest.MonkeyPatch,
    sample_task: TaskInput,
) -> None:
    module = _load_orchestrator_module()
    run_arbitrated = module.run_arbitrated

    def fake_build_reason_tree(_: TaskInput):
        return _sample_nodes()

    def fake_run_hydra_for_node(node, task, prior_node_outputs, model_call, passes=2):
        del task, prior_node_outputs, model_call, passes
        return _hydra_result(
            node.node_id,
            '{"score": 58, "breakdown": {"deal_points": 20, '
            '"price_points": 18, "turn_points": 20}, "explanation": "stub"}',
        )

    monkeypatch.setattr(module, "build_reason_tree", fake_build_reason_tree)
    monkeypatch.setattr(module, "run_hydra_for_node", fake_run_hydra_for_node)

    score_result, trace_bundle = run_arbitrated(sample_task, lambda _: "unused")

    assert isinstance(trace_bundle, list)
    assert _field(score_result, "score") is not None
    assert _field(score_result, "breakdown") is not None


def test_run_arbitrated_parses_final_score_from_last_node_output(
    monkeypatch: pytest.MonkeyPatch,
    sample_task: TaskInput,
) -> None:
    module = _load_orchestrator_module()
    run_arbitrated = module.run_arbitrated
    nodes = _sample_nodes()

    def fake_build_reason_tree(_: TaskInput):
        return nodes

    def fake_run_hydra_for_node(node, task, prior_node_outputs, model_call, passes=2):
        del task, prior_node_outputs, model_call, passes
        if node.node_id == "node-final":
            return _hydra_result(
                node.node_id,
                '{"score": 77, "breakdown": {"deal_points": 20, '
                '"price_points": 37, "turn_points": 20}, "explanation": "final"}',
            )
        return _hydra_result(node.node_id, '{"score": 1}')

    monkeypatch.setattr(module, "build_reason_tree", fake_build_reason_tree)
    monkeypatch.setattr(module, "run_hydra_for_node", fake_run_hydra_for_node)

    score_result, _ = run_arbitrated(sample_task, lambda _: "unused")
    assert _field(score_result, "score") == 77


def test_run_arbitrated_raises_or_returns_error_on_unparseable_final_output(
    monkeypatch: pytest.MonkeyPatch,
    sample_task: TaskInput,
) -> None:
    module = _load_orchestrator_module()
    run_arbitrated = module.run_arbitrated

    def fake_build_reason_tree(_: TaskInput):
        return [node for node in _sample_nodes() if node.node_id == "node-final"]

    def fake_run_hydra_for_node(node, task, prior_node_outputs, model_call, passes=2):
        del node, task, prior_node_outputs, model_call, passes
        return _hydra_result("node-final", "NOT_A_PARSEABLE_SCORE")

    monkeypatch.setattr(module, "build_reason_tree", fake_build_reason_tree)
    monkeypatch.setattr(module, "run_hydra_for_node", fake_run_hydra_for_node)

    try:
        score_result, _ = run_arbitrated(sample_task, lambda _: "unused")
    except Exception:
        return

    if isinstance(score_result, dict):
        error_observable = "error" in score_result or "parse_error" in score_result
    else:
        error_observable = hasattr(score_result, "error") or hasattr(
            score_result,
            "parse_error",
        )
    assert error_observable
