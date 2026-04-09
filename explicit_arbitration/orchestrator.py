from __future__ import annotations

from typing import Callable
from uuid import uuid4

from explicit_arbitration.hydradecide import run_hydra_for_node
from explicit_arbitration.reasontree import build_reason_tree
from explicit_arbitration.scoring_rules import ScoreResult, parse_score_result
from explicit_arbitration.traces import TraceEntry, new_trace_entry, record_trace


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _field_or_default(obj: object, name: str, default: object):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def run_arbitrated(
    task: object,
    model_call: Callable[[str], str],
) -> tuple[ScoreResult, list[TraceEntry]]:
    """Run ReasonTree -> HydraDecide sequentially and parse final score."""
    run_id = f"run-{uuid4().hex}"
    trace_entries: list[TraceEntry] = []

    nodes = build_reason_tree(task)
    record_trace(
        trace_entries,
        new_trace_entry(
            run_id=run_id,
            component="reasontree",
            step="build_reason_tree",
            input_payload={"task_id": _field(task, "task_id")},
            output_payload={
                "node_count": len(nodes),
                "node_ids": [_field(node, "node_id") for node in nodes],
            },
        ),
    )

    node_outputs: dict[str, object] = {}
    last_hydra_result: object | None = None

    for node in nodes:
        node_id = str(_field(node, "node_id"))
        hydra_result = run_hydra_for_node(
            node=node,
            task=task,
            prior_node_outputs=node_outputs,
            model_call=model_call,
            passes=2,
        )

        pass_outputs = list(_field(hydra_result, "pass_outputs"))
        pass_prompts = list(_field_or_default(hydra_result, "pass_prompts", []))
        for idx, pass_output in enumerate(pass_outputs, start=1):
            prompt = (
                str(pass_prompts[idx - 1]) if idx - 1 < len(pass_prompts) else ""
            )
            record_trace(
                trace_entries,
                new_trace_entry(
                    run_id=run_id,
                    component="hydradecide",
                    step="hydra_pass",
                    input_payload={
                        "node_id": node_id,
                        "pass_index": idx,
                        "prompt": prompt,
                    },
                    output_payload={"pass_output": str(pass_output)},
                ),
            )

        final_output = str(_field(hydra_result, "final_output"))
        record_trace(
            trace_entries,
            new_trace_entry(
                run_id=run_id,
                component="hydradecide",
                step="node_finalized",
                input_payload={"node_id": node_id},
                output_payload={"final_output": final_output},
                metadata={
                    "pass_count": int(_field(hydra_result, "pass_count")),
                },
            ),
        )

        node_outputs[node_id] = final_output
        last_hydra_result = hydra_result

    if last_hydra_result is None:
        raise ValueError("reason tree returned no nodes")

    final_raw = str(_field(last_hydra_result, "final_output"))
    score_result = parse_score_result(final_raw)

    record_trace(
        trace_entries,
        new_trace_entry(
            run_id=run_id,
            component="orchestrator",
            step="run_complete",
            input_payload={"task_id": _field(task, "task_id")},
            output_payload={
                "score": score_result.score,
                "breakdown": score_result.breakdown,
            },
        ),
    )

    return score_result, trace_entries
