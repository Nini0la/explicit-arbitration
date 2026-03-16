from __future__ import annotations

from dataclasses import dataclass


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


SAMPLE_SESSIONS: list[NegotiationSession] = [
    NegotiationSession(
        session_id="sample-deal-1",
        item_name="wireless headphones",
        reference_price=150.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 125?", 125.0),
            NegotiationTurn(1, "seller", "I can do 138.", 138.0),
            NegotiationTurn(2, "buyer", "Deal at 130.", 130.0),
        ],
        outcome="deal",
        final_price=130.0,
    ),
    NegotiationSession(
        session_id="sample-no-deal-1",
        item_name="standing desk",
        reference_price=420.0,
        turns=[
            NegotiationTurn(0, "buyer", "Can you do 250?", 250.0),
            NegotiationTurn(1, "seller", "No, too low.", None),
            NegotiationTurn(2, "buyer", "How about 300?", 300.0),
            NegotiationTurn(3, "seller", "Still too low.", None),
            NegotiationTurn(4, "buyer", "I will pass.", None),
        ],
        outcome="no_deal",
        final_price=None,
    ),
]


EXPECTED_GROUND_TRUTH: dict[str, int] = {
    "sample-deal-1": 46,
    "sample-no-deal-1": 14,
}


def get_sample_sessions() -> list[NegotiationSession]:
    return list(SAMPLE_SESSIONS)
