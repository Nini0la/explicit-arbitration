from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class HydraResult:
    node_id: str
    pass_count: int
    pass_prompts: list[str]
    pass_outputs: list[str]
    contradictions: list[str]
    revision_notes: list[str]
    final_output: str


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _build_pass_prompt(
    node: object,
    task: object,
    prior_node_outputs: dict[str, object],
    pass_index: int,
    previous_output: str,
) -> str:
    session = _field(task, "session")
    return (
        f"node_id={_field(node, 'node_id')}\n"
        f"purpose={_field(node, 'purpose')}\n"
        f"task_instruction={_field(task, 'instruction')}\n"
        f"session_id={_field(session, 'session_id')}\n"
        f"pass_index={pass_index}\n"
        f"node_prompt={_field(node, 'prompt')}\n"
        f"prior_node_outputs={prior_node_outputs}\n"
        f"previous_pass_output={previous_output}\n"
        "Return best output for this node."
    )


def run_hydra_for_node(
    node: object,
    task: object,
    prior_node_outputs: dict[str, object],
    model_call: Callable[[str], str],
    passes: int = 2,
) -> HydraResult:
    """Run sequential refinement passes for one ReasonTree node."""
    pass_count = max(1, int(passes))
    pass_prompts: list[str] = []
    pass_outputs: list[str] = []
    contradictions: list[str] = []
    revision_notes: list[str] = []

    previous_output = ""
    for index in range(pass_count):
        prompt = _build_pass_prompt(
            node=node,
            task=task,
            prior_node_outputs=prior_node_outputs,
            pass_index=index + 1,
            previous_output=previous_output,
        )
        pass_prompts.append(prompt)
        output = str(model_call(prompt))
        pass_outputs.append(output)

        if previous_output and output != previous_output:
            contradictions.append(
                f"pass_{index}_changed_from_previous"
            )
            revision_notes.append(
                f"pass_{index + 1}_revised_previous_output"
            )

        previous_output = output

    final_output = ""
    for value in reversed(pass_outputs):
        if value.strip():
            final_output = value
            break
    if not final_output:
        final_output = "{}"

    return HydraResult(
        node_id=str(_field(node, "node_id")),
        pass_count=pass_count,
        pass_prompts=pass_prompts,
        pass_outputs=pass_outputs,
        contradictions=contradictions,
        revision_notes=revision_notes,
        final_output=final_output,
    )
