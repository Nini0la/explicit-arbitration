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


def _load_build_reason_tree():
    module = importlib.import_module("explicit_arbitration.reasontree")
    return module.build_reason_tree


def _node_field(node: object, name: str):
    if isinstance(node, dict):
        return node[name]
    return getattr(node, name)


@pytest.fixture()
def valid_task() -> TaskInput:
    session = NegotiationSession(
        session_id="rt-session",
        item_name="gaming mouse",
        reference_price=80.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can we do 70?", 70.0),
            NegotiationTurn(1, "seller", "I can do 76.", 76.0),
            NegotiationTurn(2, "buyer", "Let us close at 74.", 74.0),
            NegotiationTurn(3, "seller", "Done at 74.", 74.0),
        ],
        outcome="deal",
        final_price=74.0,
    )
    return TaskInput(
        task_id="task-reasontree",
        instruction="Compute negotiation score from the session.",
        session=session,
        require_explanation=True,
    )


def test_build_reason_tree_returns_ordered_nodes_for_valid_task(
    valid_task: TaskInput,
) -> None:
    build_reason_tree = _load_build_reason_tree()
    nodes = build_reason_tree(valid_task)

    assert isinstance(nodes, list)
    assert len(nodes) >= 1

    seen_ids: set[str] = set()
    for node in nodes:
        node_id = _node_field(node, "node_id")
        depends_on = _node_field(node, "depends_on")
        assert isinstance(node_id, str)
        assert isinstance(depends_on, list)
        assert all(dep in seen_ids for dep in depends_on)
        seen_ids.add(node_id)


def test_build_reason_tree_node_count_for_scoring_task(valid_task: TaskInput) -> None:
    build_reason_tree = _load_build_reason_tree()
    nodes = build_reason_tree(valid_task)
    assert len(nodes) >= 3


def test_build_reason_tree_node_ids_are_unique(valid_task: TaskInput) -> None:
    build_reason_tree = _load_build_reason_tree()
    nodes = build_reason_tree(valid_task)
    node_ids = [_node_field(node, "node_id") for node in nodes]
    assert len(node_ids) == len(set(node_ids))


def test_build_reason_tree_dependencies_reference_prior_nodes_only(
    valid_task: TaskInput,
) -> None:
    build_reason_tree = _load_build_reason_tree()
    nodes = build_reason_tree(valid_task)

    prior_ids: set[str] = set()
    for node in nodes:
        depends_on = _node_field(node, "depends_on")
        assert all(dep in prior_ids for dep in depends_on)
        prior_ids.add(_node_field(node, "node_id"))


def test_build_reason_tree_expected_output_type_is_valid(valid_task: TaskInput) -> None:
    build_reason_tree = _load_build_reason_tree()
    nodes = build_reason_tree(valid_task)
    valid_types = {"facts", "pricing_eval", "turn_eval", "final_score"}

    for node in nodes:
        expected_output_type = _node_field(node, "expected_output_type")
        assert expected_output_type in valid_types


def test_build_reason_tree_is_deterministic_for_same_input(
    valid_task: TaskInput,
) -> None:
    build_reason_tree = _load_build_reason_tree()

    first = build_reason_tree(valid_task)
    second = build_reason_tree(valid_task)

    first_structure = [
        (
            _node_field(node, "node_id"),
            _node_field(node, "purpose"),
            _node_field(node, "prompt"),
            tuple(_node_field(node, "depends_on")),
            _node_field(node, "expected_output_type"),
        )
        for node in first
    ]
    second_structure = [
        (
            _node_field(node, "node_id"),
            _node_field(node, "purpose"),
            _node_field(node, "prompt"),
            tuple(_node_field(node, "depends_on")),
            _node_field(node, "expected_output_type"),
        )
        for node in second
    ]

    assert first_structure == second_structure
