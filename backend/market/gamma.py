"""Polymarket Gamma API — read-only market data.
Only called AFTER the swarm vote is sealed. Never touched during deliberation.
"""
from __future__ import annotations
import httpx
from ..schemas import MarketSnapshot

_GAMMA_BASE = "https://gamma-api.polymarket.com"


def get_market_snapshot(market_id: str) -> MarketSnapshot:
    """Fetch current implied probability and volume for a Polymarket market."""
    with httpx.Client(timeout=10) as c:
        r = c.get(f"{_GAMMA_BASE}/markets/{market_id}")
        r.raise_for_status()
        data = r.json()

    # Gamma API returns outcomePrices as a JSON-encoded list e.g. '["0.64", "0.36"]'
    import json as _json
    prices = _json.loads(data.get("outcomePrices", '["0.5", "0.5"]'))
    market_p = float(prices[0])   # index 0 = "Yes" / team A wins

    return MarketSnapshot(
        market_id=market_id,
        market_probability=market_p,
        volume_24h=data.get("volume24hr"),
        open_interest=data.get("openInterest"),
    )


def find_wc_market(team_a: str, team_b: str) -> str | None:
    """Search for an active WC match market. Returns market_id or None."""
    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{_GAMMA_BASE}/markets",
            params={"active": "true", "tag_id": "football", "limit": 100},
        )
        r.raise_for_status()
        markets = r.json()

    query = f"{team_a} {team_b}".lower()
    for m in markets:
        title = m.get("question", "").lower()
        if team_a.lower() in title and team_b.lower() in title:
            return m["id"]
    return None
