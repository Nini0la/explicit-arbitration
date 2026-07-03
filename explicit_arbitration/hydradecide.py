from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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


def _emit_event(
    on_event: Callable[[dict[str, object]], None] | None,
    event_type: str,
    payload: dict[str, object],
) -> None:
    if on_event is None:
        return
    on_event(
        {
            "event_type": event_type,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
    )


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
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> HydraResult:
    """Run sequential refinement passes for one ReasonTree node."""
    pass_count = max(1, int(passes))
    pass_prompts: list[str] = []
    pass_outputs: list[str] = []
    contradictions: list[str] = []
    revision_notes: list[str] = []

    previous_output = ""
    for index in range(pass_count):
        node_id = str(_field(node, "node_id"))
        pass_index = index + 1
        prompt = _build_pass_prompt(
            node=node,
            task=task,
            prior_node_outputs=prior_node_outputs,
            pass_index=pass_index,
            previous_output=previous_output,
        )
        _emit_event(
            on_event,
            "pass_started",
            {
                "component": "hydradecide",
                "node_id": node_id,
                "pass_index": pass_index,
                "prompt": prompt,
            },
        )
        pass_prompts.append(prompt)
        output = str(model_call(prompt))
        _emit_event(
            on_event,
            "pass_completed",
            {
                "component": "hydradecide",
                "node_id": node_id,
                "pass_index": pass_index,
                "pass_output": output,
            },
        )
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
