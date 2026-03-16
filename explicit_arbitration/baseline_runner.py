from __future__ import annotations

from typing import Callable

from explicit_arbitration.scoring_rules import ScoreResult, parse_score_result


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def run_baseline(
    task: object,
    model_call: Callable[[str], str],
) -> ScoreResult:
    """Run direct single-pass model scoring without ReasonTree/HydraDecide."""
    session = _field(task, "session")
    prompt = (
        f"task_id={_field(task, 'task_id')}\n"
        f"instruction={_field(task, 'instruction')}\n"
        f"session_id={_field(session, 'session_id')}\n"
        f"item_name={_field(session, 'item_name')}\n"
        f"reference_price={_field(session, 'reference_price')}\n"
        f"outcome={_field(session, 'outcome')}\n"
        f"final_price={_field(session, 'final_price')}\n"
        f"turn_count={len(_field(session, 'turns'))}\n"
        "Return strict JSON with score, breakdown, explanation."
    )
    raw_output = model_call(prompt)
    return parse_score_result(raw_output)
