from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, is_dataclass
from typing import Callable

from explicit_arbitration.baseline_runner import run_baseline
from explicit_arbitration.model_client import (
    call_openai_compatible,
    load_live_model_config,
)
from explicit_arbitration.orchestrator import run_arbitrated
from explicit_arbitration.sample_sessions import get_sample_sessions
from explicit_arbitration.scoring_rules import compute_ground_truth_score


@dataclass(slots=True)
class TaskInput:
    task_id: str
    instruction: str
    session: object
    require_explanation: bool = True


def _repair_prompt_for_json(raw_output: str) -> str:
    return (
        "Your previous output was not valid JSON for the required schema. "
        "Return strict JSON only with keys: score, breakdown, explanation.\n"
        f"previous_output={raw_output}"
    )


def _build_model_call(
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[Callable[[str], str], dict[str, object]]:
    config = load_live_model_config(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    def _live_model_call(prompt: str) -> str:
        first = call_openai_compatible(prompt, config)
        try:
            json.loads(first)
            return first
        except json.JSONDecodeError:
            repaired = call_openai_compatible(_repair_prompt_for_json(first), config)
            return repaired

    return _live_model_call, {
        "mode": "live",
        "provider": "openai_compatible_chat_completions",
        "model": config.model,
        "base_url": config.base_url,
        "api_key_source": config.api_key_source,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }


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
    on_event({"event_type": event_type, **payload})


def _to_primitive(value: object) -> object:
    if is_dataclass(value):
        return {k: _to_primitive(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _to_primitive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_primitive(v) for v in value]
    return value


def _serialize_trace_entry(entry: object) -> dict[str, object]:
    return {
        "run_id": str(_field(entry, "run_id")),
        "timestamp_utc": str(_field(entry, "timestamp_utc")),
        "component": str(_field(entry, "component")),
        "step": str(_field(entry, "step")),
        "input_payload": _to_primitive(_field(entry, "input_payload")),
        "output_payload": _to_primitive(_field(entry, "output_payload")),
        "metadata": _to_primitive(_field(entry, "metadata")),
    }


def _build_trace_summary(trace_bundle: list[object]) -> dict[str, object]:
    reason_tree_nodes = 0
    node_sequence: list[str] = []
    hydra_pass_count = 0
    final_node_output: str | None = None

    for entry in trace_bundle:
        component = str(_field(entry, "component"))
        step = str(_field(entry, "step"))
        output_payload = _field(entry, "output_payload")
        input_payload = _field(entry, "input_payload")

        if component == "reasontree" and step == "build_reason_tree":
            node_count = output_payload.get("node_count", 0)
            reason_tree_nodes = int(node_count)
            node_ids = output_payload.get("node_ids", [])
            node_sequence = [str(node_id) for node_id in node_ids]

        if component == "hydradecide" and step == "hydra_pass":
            hydra_pass_count += 1

        if component == "hydradecide" and step == "node_finalized":
            node_id = str(input_payload.get("node_id", ""))
            if node_id == "node-final" or not final_node_output:
                final_node_output = str(output_payload.get("final_output", ""))

    return {
        "reason_tree_node_count": reason_tree_nodes,
        "reason_tree_node_sequence": node_sequence,
        "hydra_pass_count": hydra_pass_count,
        "final_node_output": final_node_output,
    }


def _session_turns(session: object) -> list[dict[str, object]]:
    turns = _field(session, "turns")
    result: list[dict[str, object]] = []
    for turn in turns:
        result.append(
            {
                "turn_index": int(_field(turn, "turn_index")),
                "speaker": str(_field(turn, "speaker")),
                "message": str(_field(turn, "message")),
                "offer_price": _field(turn, "offer_price"),
            }
        )
    return result


def run_demo() -> dict[str, object]:
    return run_demo_with_model()


def run_demo_with_model(
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    model_call, model_mode = _build_model_call(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    _emit_event(on_event, "model_configured", model_mode)
    return run_demo_with_model_call(
        model_call=model_call,
        model_mode=model_mode,
        on_event=on_event,
    )


def run_demo_with_model_call(
    model_call: Callable[[str], str],
    model_mode: dict[str, object] | None = None,
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    sessions = get_sample_sessions()
    if not sessions:
        raise ValueError("sample_sessions returned no sessions")

    session = sessions[0]
    task = TaskInput(
        task_id=f"task-{session.session_id}",
        instruction="Score this negotiation session.",
        session=session,
        require_explanation=True,
    )

    _emit_event(on_event, "ground_truth_started", {"task_id": task.task_id})
    ground_truth = compute_ground_truth_score(task.session)
    _emit_event(
        on_event,
        "ground_truth_completed",
        {"task_id": task.task_id, "score": ground_truth.score},
    )

    _emit_event(on_event, "baseline_started", {"task_id": task.task_id})
    baseline = run_baseline(task, model_call)
    _emit_event(
        on_event,
        "baseline_completed",
        {"task_id": task.task_id, "score": baseline.score},
    )

    _emit_event(on_event, "arbitration_started", {"task_id": task.task_id})
    arbitrated, trace_bundle = run_arbitrated(task, model_call, on_event=on_event)
    _emit_event(
        on_event,
        "arbitration_completed",
        {"task_id": task.task_id, "score": arbitrated.score},
    )
    serialized_trace = [_serialize_trace_entry(entry) for entry in trace_bundle]
    trace_summary = _build_trace_summary(trace_bundle)

    return {
        "session_id": session.session_id,
        "task_id": task.task_id,
        "model_mode": model_mode or {"mode": "injected_test_double"},
        "ground_truth_score": ground_truth.score,
        "baseline_score": baseline.score,
        "arbitrated_score": arbitrated.score,
        "baseline_match": baseline.score == ground_truth.score,
        "arbitrated_match": arbitrated.score == ground_truth.score,
        "trace_entry_count": len(trace_bundle),
        "session_turns": _session_turns(session),
        "arbitration_trace_summary": trace_summary,
        "arbitration_trace_entries": serialized_trace,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic scorer, baseline, and live-model arbitrated "
            "comparison for one sample session."
        )
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (or set MODEL_NAME env var).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Max tokens per call.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature.",
    )
    return parser.parse_args()


def _print_cli_event(event: dict[str, object]) -> None:
    event_type = str(event.get("event_type", ""))
    if event_type == "model_configured":
        message = (
            "[model] "
            f"{event.get('model')} via {event.get('base_url')} "
            f"({event.get('api_key_source')})"
        )
    elif event_type == "ground_truth_started":
        message = "[ground-truth] computing deterministic score"
    elif event_type == "ground_truth_completed":
        message = f"[ground-truth] score={event.get('score')}"
    elif event_type == "baseline_started":
        message = "[baseline] requesting single-pass model score"
    elif event_type == "baseline_completed":
        message = f"[baseline] score={event.get('score')}"
    elif event_type == "arbitration_started":
        message = "[arbitration] starting ReasonTree + HydraDecide"
    elif event_type == "reasontree_built":
        node_ids = ", ".join(str(node) for node in event.get("node_ids", []))
        message = f"[reasontree] built {event.get('node_count')} nodes: {node_ids}"
    elif event_type == "node_started":
        message = f"[hydradecide] node {event.get('node_id')} started"
    elif event_type == "pass_started":
        message = (
            "[hydradecide] "
            f"{event.get('node_id')} pass {event.get('pass_index')} started"
        )
    elif event_type == "pass_completed":
        message = (
            "[hydradecide] "
            f"{event.get('node_id')} pass {event.get('pass_index')} completed"
        )
    elif event_type == "node_finalized":
        message = f"[hydradecide] node {event.get('node_id')} finalized"
    elif event_type == "run_completed":
        message = f"[orchestrator] final score={event.get('score')}"
    elif event_type == "arbitration_completed":
        message = f"[arbitration] completed score={event.get('score')}"
    else:
        return
    print(message, file=sys.stderr, flush=True)


def main() -> None:
    args = _parse_args()
    try:
        artifact = run_demo_with_model(
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            on_event=_print_cli_event,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from None
    print(json.dumps(artifact, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
