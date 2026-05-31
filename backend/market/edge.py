"""Edge detection — compares swarm consensus to Polymarket implied probability."""
from __future__ import annotations
from ..config import settings
from ..schemas import MarketSnapshot, BetReceipt
from .gamma import get_market_snapshot
from .clob import place_limit_order


def detect_and_act(
    swarm_p: float,
    market_id: str,
    bet_size: float = 10.0,
) -> tuple[MarketSnapshot, float, bool, BetReceipt | None]:
    """
    Returns (snapshot, spread, edge_detected, bet_receipt).
    Polymarket is queried here for the first and only time in the pipeline.
    """
    snapshot = get_market_snapshot(market_id)
    spread = abs(swarm_p - snapshot.market_probability)
    edge_detected = spread > settings.edge_threshold

    bet_receipt = None
    if edge_detected:
        side = "BUY" if swarm_p > snapshot.market_probability else "SELL"
        price = swarm_p if side == "BUY" else (1 - swarm_p)
        try:
            bet_receipt = place_limit_order(market_id, side, bet_size, price)
        except NotImplementedError:
            pass  # demo mode: show would-be order without executing

    return snapshot, spread, edge_detected, bet_receipt
