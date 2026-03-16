from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(slots=True)
class ScoreResult:
    score: int
    breakdown: dict[str, int]
    explanation: str | None


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def compute_ground_truth_score(session: object) -> ScoreResult:
    """Compute deterministic score using the v1 SPEC formula."""
    outcome = _field(session, "outcome")
    final_price = _field(session, "final_price")
    reference_price = float(_field(session, "reference_price"))
    turn_count = len(_field(session, "turns"))

    if outcome == "no_deal" or final_price is None:
        deal_points = 0
        price_points = 0
    else:
        deal_points = 20
        savings_ratio = (reference_price - float(final_price)) / reference_price
        savings_ratio = max(0.0, min(1.0, savings_ratio))
        price_points = round(60 * savings_ratio)

    turn_points = max(0, 20 - max(0, turn_count - 2) * 2)
    score = max(0, min(100, deal_points + price_points + turn_points))

    breakdown = {
        "deal_points": int(deal_points),
        "price_points": int(price_points),
        "turn_points": int(turn_points),
    }
    explanation = (
        "deterministic_scoring_v1"
        f"(deal={breakdown['deal_points']},price={breakdown['price_points']},"
        f"turns={breakdown['turn_points']})"
    )
    return ScoreResult(score=int(score), breakdown=breakdown, explanation=explanation)


def parse_score_result(raw_output: str) -> ScoreResult:
    """Parse model score output from JSON into ScoreResult."""
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ValueError(f"unparseable score output: {raw_output}") from exc

    if not isinstance(payload, dict):
        raise ValueError("score output must be a JSON object")

    if "score" not in payload or "breakdown" not in payload:
        raise ValueError("score output must include 'score' and 'breakdown'")

    score = int(payload["score"])
    breakdown_raw = payload["breakdown"]
    if not isinstance(breakdown_raw, dict):
        raise ValueError("breakdown must be a JSON object")

    breakdown = {
        "deal_points": int(breakdown_raw.get("deal_points", 0)),
        "price_points": int(breakdown_raw.get("price_points", 0)),
        "turn_points": int(breakdown_raw.get("turn_points", 0)),
    }

    explanation_raw = payload.get("explanation")
    explanation = str(explanation_raw) if explanation_raw is not None else None

    return ScoreResult(score=score, breakdown=breakdown, explanation=explanation)
