from __future__ import annotations

import inspect
from datetime import datetime, timezone
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


def run_arbitrated(
    task: object,
    model_call: Callable[[str], str],
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> tuple[ScoreResult, list[TraceEntry]]:
    """Run ReasonTree -> HydraDecide sequentially and parse final score."""
    run_id = f"run-{uuid4().hex}"
    trace_entries: list[TraceEntry] = []
    _emit_event(
        on_event,
        "run_started",
        {
            "component": "orchestrator",
            "run_id": run_id,
            "task_id": str(_field(task, "task_id")),
        },
    )

    nodes = build_reason_tree(task)
    _emit_event(
        on_event,
        "reasontree_built",
        {
            "component": "reasontree",
            "run_id": run_id,
            "node_count": len(nodes),
            "node_ids": [str(_field(node, "node_id")) for node in nodes],
        },
    )
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
        _emit_event(
            on_event,
            "node_started",
            {
                "component": "orchestrator",
                "run_id": run_id,
                "node_id": node_id,
            },
        )
        hydra_kwargs = {
            "node": node,
            "task": task,
            "prior_node_outputs": node_outputs,
            "model_call": model_call,
            "passes": 2,
        }
        parameters = inspect.signature(run_hydra_for_node).parameters
        if "on_event" in parameters:
            hydra_kwargs["on_event"] = on_event
        hydra_result = run_hydra_for_node(**hydra_kwargs)

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
        _emit_event(
            on_event,
            "node_finalized",
            {
                "component": "orchestrator",
                "run_id": run_id,
                "node_id": node_id,
                "final_output": final_output,
            },
        )

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
    _emit_event(
        on_event,
        "run_completed",
        {
            "component": "orchestrator",
            "run_id": run_id,
            "task_id": str(_field(task, "task_id")),
            "score": score_result.score,
        },
    )

    return score_result, trace_entries
