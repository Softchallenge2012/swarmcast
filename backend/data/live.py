"""Live data fetchers — football-data.org, Transfermarkt scraper, API-Football.
All results cached for the demo session duration (TTL = 1h).
Polymarket is explicitly excluded — it is never queried here.
"""
from __future__ import annotations
import time
import httpx
from ..config import settings

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 3600  # seconds


def _cached(key: str, fn):
    now = time.time()
    if key in _cache and now - _cache[key][0] < _TTL:
        return _cache[key][1]
    result = fn()
    _cache[key] = (now, result)
    return result


# ── football-data.org ─────────────────────────────────────────────────────────

_FD_BASE = "https://api.football-data.org/v4"
_FD_HEADERS = {"X-Auth-Token": settings.football_data_api_key}


def get_form(team_id: int) -> dict:
    """Last 5 results for a team."""
    def fetch():
        with httpx.Client() as c:
            r = c.get(f"{_FD_BASE}/teams/{team_id}/matches?limit=5&status=FINISHED",
                      headers=_FD_HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
    return _cached(f"form:{team_id}", fetch)


def get_standings(competition_id: str) -> dict:
    """Group standings for a competition."""
    def fetch():
        with httpx.Client() as c:
            r = c.get(f"{_FD_BASE}/competitions/{competition_id}/standings",
                      headers=_FD_HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
    return _cached(f"standings:{competition_id}", fetch)


# ── API-Football (H2H backup) ─────────────────────────────────────────────────

_AF_BASE = "https://v3.football.api-sports.io"
_AF_HEADERS = {"x-apisports-key": settings.api_football_key}


def get_h2h(team_a_id: int, team_b_id: int) -> dict:
    def fetch():
        with httpx.Client() as c:
            r = c.get(f"{_AF_BASE}/fixtures/headtohead",
                      headers=_AF_HEADERS,
                      params={"h2h": f"{team_a_id}-{team_b_id}", "last": 10},
                      timeout=10)
            r.raise_for_status()
            return r.json()
    return _cached(f"h2h:{team_a_id}:{team_b_id}", fetch)


# ── Transfermarkt scraper (injuries / suspensions) ────────────────────────────

def get_injuries(team_name: str) -> dict:
    """Stub — wire transfermarkt-scraper library when available."""
    # TODO: integrate transfermarkt-scraper
    return {"team": team_name, "injuries": [], "suspensions": []}


# ── Context bundle builder ────────────────────────────────────────────────────

def build_context_bundle(
    team_a_id: int,
    team_b_id: int,
    team_a_name: str,
    team_b_name: str,
    competition_id: str,
) -> dict[str, str]:
    """Return a dict keyed by data_slice_id for injection into specialist prompts."""
    import json

    form_a    = get_form(team_a_id)
    form_b    = get_form(team_b_id)
    h2h       = get_h2h(team_a_id, team_b_id)
    standings = get_standings(competition_id)
    injuries_a = get_injuries(team_a_name)
    injuries_b = get_injuries(team_b_name)

    return {
        "live_form":      json.dumps({"team_a": form_a, "team_b": form_b}, default=str),
        "live_injuries":  json.dumps({"team_a": injuries_a, "team_b": injuries_b}),
        "live_standings": json.dumps(standings, default=str),
        "kaggle_history": json.dumps(h2h, default=str),   # supplemented by RAG at query time
        "statsbomb":      "",   # injected from RAG layer
    }
