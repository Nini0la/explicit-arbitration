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


@dataclass(slots=True)
class ReasonTreeNode:
    node_id: str
    purpose: str
    prompt: str
    depends_on: list[str]
    expected_output_type: str


def _load_run_hydra_for_node():
    module = importlib.import_module("explicit_arbitration.hydradecide")
    return module.run_hydra_for_node


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


@pytest.fixture()
def sample_task() -> TaskInput:
    session = NegotiationSession(
        session_id="hydra-session",
        item_name="laptop stand",
        reference_price=60.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 45?", 45.0),
            NegotiationTurn(1, "seller", "I can do 52.", 52.0),
        ],
        outcome="deal",
        final_price=52.0,
    )
    return TaskInput(
        task_id="task-hydra",
        instruction="Evaluate one scoring node.",
        session=session,
        require_explanation=True,
    )


@pytest.fixture()
def sample_node() -> ReasonTreeNode:
    return ReasonTreeNode(
        node_id="node-final",
        purpose="Compute final score",
        prompt="Compute final score from prior outputs and session context.",
        depends_on=["node-facts", "node-pricing", "node-turns"],
        expected_output_type="final_score",
    )


@pytest.fixture()
def prior_node_outputs() -> dict[str, object]:
    return {
        "node-facts": "upstream-signal: facts",
        "node-pricing": "upstream-signal: pricing",
        "node-turns": "upstream-signal: turns",
    }


def test_run_hydra_for_node_uses_configured_pass_count(
    sample_node: ReasonTreeNode,
    sample_task: TaskInput,
    prior_node_outputs: dict[str, object],
) -> None:
    run_hydra_for_node = _load_run_hydra_for_node()

    def model_call(_: str) -> str:
        return "stub-response"

    result = run_hydra_for_node(
        sample_node,
        sample_task,
        prior_node_outputs,
        model_call,
        passes=3,
    )
    assert _field(result, "pass_count") == 3


def test_run_hydra_for_node_returns_non_empty_final_output(
    sample_node: ReasonTreeNode,
    sample_task: TaskInput,
    prior_node_outputs: dict[str, object],
) -> None:
    run_hydra_for_node = _load_run_hydra_for_node()

    def model_call(_: str) -> str:
        return "final-score: 66"

    result = run_hydra_for_node(
        sample_node,
        sample_task,
        prior_node_outputs,
        model_call,
    )
    final_output = _field(result, "final_output")

    assert isinstance(final_output, str)
    assert final_output.strip() != ""


def test_run_hydra_for_node_preserves_node_id(
    sample_node: ReasonTreeNode,
    sample_task: TaskInput,
    prior_node_outputs: dict[str, object],
) -> None:
    run_hydra_for_node = _load_run_hydra_for_node()

    def model_call(_: str) -> str:
        return "stub-response"

    result = run_hydra_for_node(
        sample_node,
        sample_task,
        prior_node_outputs,
        model_call,
    )
    assert _field(result, "node_id") == sample_node.node_id


def test_run_hydra_for_node_includes_contradictions_and_revision_notes_fields(
    sample_node: ReasonTreeNode,
    sample_task: TaskInput,
    prior_node_outputs: dict[str, object],
) -> None:
    run_hydra_for_node = _load_run_hydra_for_node()

    def model_call(_: str) -> str:
        return "stub-response"

    result = run_hydra_for_node(
        sample_node,
        sample_task,
        prior_node_outputs,
        model_call,
    )

    contradictions = _field(result, "contradictions")
    revision_notes = _field(result, "revision_notes")

    assert isinstance(contradictions, list)
    assert isinstance(revision_notes, list)


def test_run_hydra_for_node_receives_prior_node_outputs(
    sample_node: ReasonTreeNode,
    sample_task: TaskInput,
    prior_node_outputs: dict[str, object],
) -> None:
    run_hydra_for_node = _load_run_hydra_for_node()
    prompts: list[str] = []

    def model_call(prompt: str) -> str:
        prompts.append(prompt)
        return "stub-response"

    run_hydra_for_node(
        sample_node,
        sample_task,
        prior_node_outputs,
        model_call,
        passes=2,
    )

    expected_token = "upstream-signal"
    assert any(expected_token in prompt for prompt in prompts)


def test_run_hydra_for_node_with_stub_model_call(
    sample_node: ReasonTreeNode,
    sample_task: TaskInput,
    prior_node_outputs: dict[str, object],
) -> None:
    run_hydra_for_node = _load_run_hydra_for_node()
    call_count = 0

    def model_call(_: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"stub-pass-{call_count}"

    result = run_hydra_for_node(
        sample_node,
        sample_task,
        prior_node_outputs,
        model_call,
    )
    pass_count = _field(result, "pass_count")

    assert call_count >= 1
    assert pass_count >= 2
