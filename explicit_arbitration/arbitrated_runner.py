from __future__ import annotations

import json
from dataclasses import dataclass

from explicit_arbitration.baseline_runner import run_baseline
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


def run_demo() -> dict[str, object]:
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

    ground_truth = compute_ground_truth_score(task.session)
    baseline = run_baseline(task, _stub_model_call)
    arbitrated, trace_bundle = run_arbitrated(task, _stub_model_call)

    return {
        "session_id": session.session_id,
        "ground_truth_score": ground_truth.score,
        "baseline_score": baseline.score,
        "arbitrated_score": arbitrated.score,
        "baseline_match": baseline.score == ground_truth.score,
        "arbitrated_match": arbitrated.score == ground_truth.score,
        "trace_entry_count": len(trace_bundle),
    }


def main() -> None:
    artifact = run_demo()
    print(json.dumps(artifact, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
