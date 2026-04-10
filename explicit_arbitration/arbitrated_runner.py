from __future__ import annotations

import argparse
import json
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


def _stub_model_call(_: str) -> str:
    return (
        '{"score": 61, "breakdown": {"deal_points": 20, '
        '"price_points": 21, "turn_points": 20}, "explanation": "stub"}'
    )


def _repair_prompt_for_json(raw_output: str) -> str:
    return (
        "Your previous output was not valid JSON for the required schema. "
        "Return strict JSON only with keys: score, breakdown, explanation.\n"
        f"previous_output={raw_output}"
    )


def _build_model_call(
    use_live_model: bool,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[Callable[[str], str], dict[str, object]]:
    if not use_live_model:
        return _stub_model_call, {"mode": "stub"}

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
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


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
    return run_demo_with_model(use_live_model=False)


def run_demo_with_model(
    use_live_model: bool,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
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
    model_call, model_mode = _build_model_call(
        use_live_model=use_live_model,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    ground_truth = compute_ground_truth_score(task.session)
    baseline = run_baseline(task, model_call)
    arbitrated, trace_bundle = run_arbitrated(task, model_call)
    serialized_trace = [_serialize_trace_entry(entry) for entry in trace_bundle]
    trace_summary = _build_trace_summary(trace_bundle)

    return {
        "session_id": session.session_id,
        "task_id": task.task_id,
        "model_mode": model_mode,
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
            "Run deterministic scorer, baseline, and arbitrated comparison for one "
            "sample session."
        )
    )
    parser.add_argument(
        "--use-live-model",
        action="store_true",
        help="Use real OpenAI-compatible model calls instead of stub responses.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name for live mode (or set MODEL_NAME env var).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Max tokens per call for live mode.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature for live mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = run_demo_with_model(
        use_live_model=bool(args.use_live_model),
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    print(json.dumps(artifact, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
