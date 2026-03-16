from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest


@dataclass(slots=True)
class NegotiationTurn:
    turn_index: int
    speaker: str
    message: str
    offer_price: float | None


@dataclass(slots=True)
class NegotiationSession:
    session_id: str
    item_name: str
    reference_price: float
    turns: list[NegotiationTurn]
    outcome: str
    final_price: float | None


def _load_compute_ground_truth_score():
    module = importlib.import_module("explicit_arbitration.scoring_rules")
    return module.compute_ground_truth_score


def _field(obj: object, name: str):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


@pytest.fixture()
def known_deal_session() -> NegotiationSession:
    return NegotiationSession(
        session_id="s-deal",
        item_name="headphones",
        reference_price=100.0,
        turns=[
            NegotiationTurn(0, "buyer", "Hi, can you do 90?", 90.0),
            NegotiationTurn(1, "seller", "Best is 88.", 88.0),
            NegotiationTurn(2, "buyer", "What about 82?", 82.0),
            NegotiationTurn(3, "seller", "Deal at 80.", 80.0),
        ],
        outcome="deal",
        final_price=80.0,
    )


@pytest.fixture()
def known_no_deal_session() -> NegotiationSession:
    return NegotiationSession(
        session_id="s-no-deal",
        item_name="desk lamp",
        reference_price=120.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can we do 70?", 70.0),
            NegotiationTurn(1, "seller", "No, too low.", None),
            NegotiationTurn(2, "buyer", "Then I will pass.", None),
        ],
        outcome="no_deal",
        final_price=None,
    )


def test_compute_ground_truth_score_known_sessions_exact_values(
    known_deal_session: NegotiationSession,
    known_no_deal_session: NegotiationSession,
) -> None:
    compute_ground_truth_score = _load_compute_ground_truth_score()

    deal_result = compute_ground_truth_score(known_deal_session)
    no_deal_result = compute_ground_truth_score(known_no_deal_session)

    assert _field(deal_result, "score") == 48
    assert _field(no_deal_result, "score") == 18

    deal_breakdown = _field(deal_result, "breakdown")
    no_deal_breakdown = _field(no_deal_result, "breakdown")
    assert deal_breakdown == {"deal_points": 20, "price_points": 12, "turn_points": 16}
    assert no_deal_breakdown == {"deal_points": 0, "price_points": 0, "turn_points": 18}


def test_compute_ground_truth_score_no_deal_zero_deal_and_price_points(
    known_no_deal_session: NegotiationSession,
) -> None:
    compute_ground_truth_score = _load_compute_ground_truth_score()
    result = compute_ground_truth_score(known_no_deal_session)
    breakdown = _field(result, "breakdown")

    assert breakdown["deal_points"] == 0
    assert breakdown["price_points"] == 0


def test_compute_ground_truth_score_is_deterministic(
    known_deal_session: NegotiationSession,
) -> None:
    compute_ground_truth_score = _load_compute_ground_truth_score()

    first = compute_ground_truth_score(known_deal_session)
    second = compute_ground_truth_score(known_deal_session)

    assert _field(first, "score") == _field(second, "score")
    assert _field(first, "breakdown") == _field(second, "breakdown")
    assert _field(first, "explanation") == _field(second, "explanation")


def test_compute_ground_truth_score_zero_turns() -> None:
    compute_ground_truth_score = _load_compute_ground_truth_score()
    session = NegotiationSession(
        session_id="s-zero-turns",
        item_name="monitor",
        reference_price=200.0,
        turns=[],
        outcome="deal",
        final_price=180.0,
    )

    result = compute_ground_truth_score(session)
    breakdown = _field(result, "breakdown")

    assert breakdown == {"deal_points": 20, "price_points": 6, "turn_points": 20}
    assert _field(result, "score") == 46


def test_compute_ground_truth_score_final_price_none_with_no_deal() -> None:
    compute_ground_truth_score = _load_compute_ground_truth_score()
    session = NegotiationSession(
        session_id="s-none-price",
        item_name="keyboard",
        reference_price=50.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 30?", 30.0),
            NegotiationTurn(1, "seller", "No, sorry.", None),
        ],
        outcome="no_deal",
        final_price=None,
    )

    result = compute_ground_truth_score(session)
    breakdown = _field(result, "breakdown")

    assert breakdown["deal_points"] == 0
    assert breakdown["price_points"] == 0
    assert breakdown["turn_points"] == 20
    assert _field(result, "score") == 20
