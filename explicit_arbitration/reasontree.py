from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReasonTreeNode:
    node_id: str
    purpose: str
    prompt: str
    depends_on: list[str]
    expected_output_type: str


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def build_reason_tree(task: object) -> list[ReasonTreeNode]:
    """Build deterministic scoring decomposition for one negotiation task."""
    instruction = str(_field(task, "instruction"))
    session = _field(task, "session")
    session_id = _field(session, "session_id")

    return [
        ReasonTreeNode(
            node_id="node-facts",
            purpose="Extract negotiation facts",
            prompt=(
                f"{instruction}\n"
                f"Session={session_id}. Extract key negotiation facts from the turns."
            ),
            depends_on=[],
            expected_output_type="facts",
        ),
        ReasonTreeNode(
            node_id="node-pricing",
            purpose="Evaluate pricing against reference",
            prompt=(
                "Using extracted facts, evaluate price quality versus reference price."
            ),
            depends_on=["node-facts"],
            expected_output_type="pricing_eval",
        ),
        ReasonTreeNode(
            node_id="node-turns",
            purpose="Evaluate turn efficiency",
            prompt=(
                "Using extracted facts, evaluate turn efficiency and negotiation "
                "length."
            ),
            depends_on=["node-facts"],
            expected_output_type="turn_eval",
        ),
        ReasonTreeNode(
            node_id="node-final",
            purpose="Compute final score",
            prompt=(
                "Compute final score JSON with fields: score, breakdown, explanation "
                "from prior node outputs."
            ),
            depends_on=["node-facts", "node-pricing", "node-turns"],
            expected_output_type="final_score",
        ),
    ]
