"""Delphi aggregation — confidence-weighted consensus, 80% CI, minority dissent detection."""
from __future__ import annotations
import asyncio
import numpy as np
from ..schemas import AgentVote, ConsensusResult, SpecialistDefinition
from .specialists import run_swarm


def _weighted_consensus(votes: list[AgentVote]) -> tuple[float, float, float]:
    """Return (mean_p, ci_low, ci_high) using confidence as weights."""
    probs = np.array([v.probability for v in votes])
    weights = np.array([v.confidence for v in votes])
    weights = weights / weights.sum()

    mean_p = float(np.average(probs, weights=weights))
    # Weighted std for 80% CI (~1.28 sigma)
    variance = float(np.average((probs - mean_p) ** 2, weights=weights))
    std = variance ** 0.5
    ci_low  = max(0.0, mean_p - 1.28 * std)
    ci_high = min(1.0, mean_p + 1.28 * std)
    return mean_p, ci_low, ci_high


def _minority_dissent(votes: list[AgentVote], mean_p: float, std: float) -> list[AgentVote]:
    """Votes more than 1 std-dev from the consensus are flagged as minority dissent."""
    if std < 1e-6:
        return []
    return [v for v in votes if abs(v.probability - mean_p) > std]


def aggregate(votes: list[AgentVote]) -> ConsensusResult:
    mean_p, ci_low, ci_high = _weighted_consensus(votes)
    probs = np.array([v.probability for v in votes])
    std = float(np.std(probs))
    dissent = _minority_dissent(votes, mean_p, std)
    return ConsensusResult(
        probability=mean_p,
        ci_low=ci_low,
        ci_high=ci_high,
        minority_dissent=dissent,
        all_votes=votes,
    )


async def run_delphi_round(
    specialists: list[SpecialistDefinition],
    round1_votes: list[AgentVote],
    contexts: dict[str, str],
) -> list[AgentVote]:
    """Build Delphi signal (aggregate P distribution, no reasoning chains) and fire round 2."""
    mean_p, ci_low, ci_high = _weighted_consensus(round1_votes)
    # Sparse signal: aggregate stats only, no individual reasoning exposed
    delphi_addendum = (
        f"\n\n[DELPHI SIGNAL] Panel aggregate after round 1: "
        f"P={mean_p:.3f}, 80% CI [{ci_low:.3f}, {ci_high:.3f}]. "
        f"Revise your estimate if your assigned data warrants it. "
        f"Do not anchor to this figure without independent justification."
    )
    delphi_specialists = [
        SpecialistDefinition(
            role=s.role,
            system_prompt=s.system_prompt + delphi_addendum,
            data_slice_id=s.data_slice_id,
        )
        for s in specialists
    ]
    return await run_swarm(delphi_specialists, contexts, round=2)
