"""Meta-orchestrator: reads a match query, writes specialist definitions,
acts on critic output (spawn / rewrite / broadcast)."""
from __future__ import annotations
import json
import anthropic
import weave
from ..config import settings
from ..schemas import CritiqueOutput, CriticAction, RecommendedAction, SpecialistDefinition

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Fallback pool used when LLM spawn fails or for testing
FALLBACK_SPECIALISTS: list[dict] = [
    {"role": "tactical_analyst",      "data_slice_id": "statsbomb"},
    {"role": "historical_stats",      "data_slice_id": "kaggle_history"},
    {"role": "current_form",          "data_slice_id": "live_form"},
    {"role": "squad_fitness",         "data_slice_id": "live_injuries"},
    {"role": "tournament_context",    "data_slice_id": "live_standings"},
    {"role": "contrarian",            "data_slice_id": "kaggle_history"},
]

_SPAWN_SYSTEM = """\
You are a meta-orchestrator for a multi-agent sports forecasting system.
Given a match question, return a JSON array of specialist agent definitions.
Each element must have exactly three fields:
  "role"           – short snake_case label
  "system_prompt"  – full system prompt for that specialist (≤400 tokens)
  "data_slice_id"  – one of: statsbomb | kaggle_history | live_form | live_injuries | live_standings

Rules:
- Always include a "contrarian" agent biased against the favourite.
- Each system prompt must include the sentence:
  "Form your own independent view based solely on your assigned data.
   Do not speculate about what other analysts might conclude."
- No agent prompt may reference Polymarket, betting odds, or market-implied probability.
- Return ONLY the JSON array, no prose, no markdown fences.
"""


@weave.op()
def spawn_specialists(match_query: str) -> list[SpecialistDefinition]:
    """Ask the orchestrator LLM to write specialist definitions for this match."""
    response = client.messages.create(
        model=settings.orchestrator_model,
        max_tokens=2048,
        system=_SPAWN_SYSTEM,
        messages=[{"role": "user", "content": match_query}],
    )
    raw = response.content[0].text.strip()
    try:
        definitions = json.loads(raw)
        return [SpecialistDefinition(**d) for d in definitions]
    except Exception:
        # Fallback: hardcoded pool with empty prompts — prompts written separately
        return [
            SpecialistDefinition(role=s["role"], system_prompt="", data_slice_id=s["data_slice_id"])
            for s in FALLBACK_SPECIALISTS
        ]


@weave.op()
def act_on_critique(
    critique: CritiqueOutput,
    specialists: list[SpecialistDefinition],
    match_query: str,
) -> list[SpecialistDefinition]:
    """Apply critic recommendations: spawn new agents, rewrite prompts, or broadcast gap signal."""
    updated = list(specialists)

    for rec in critique.recommended_actions:
        if rec.action == CriticAction.spawn:
            new_def = _spawn_single(rec.rationale, match_query)
            if new_def:
                updated.append(new_def)

        elif rec.action == CriticAction.rewrite and rec.target_role:
            for i, s in enumerate(updated):
                if s.role == rec.target_role:
                    updated[i] = _rewrite_prompt(s, rec.rationale, match_query)

        elif rec.action == CriticAction.broadcast:
            addendum = f"\n\n[SYSTEM ADDENDUM] {rec.rationale}"
            updated = [
                SpecialistDefinition(
                    role=s.role,
                    system_prompt=s.system_prompt + addendum,
                    data_slice_id=s.data_slice_id,
                )
                for s in updated
            ]

    return updated


def _spawn_single(rationale: str, match_query: str) -> SpecialistDefinition | None:
    prompt = (
        f"Match: {match_query}\n\n"
        f"Gap identified by critic: {rationale}\n\n"
        "Return a single specialist definition as a JSON object with fields: "
        "role, system_prompt, data_slice_id. No prose."
    )
    response = client.messages.create(
        model=settings.orchestrator_model,
        max_tokens=512,
        system=_SPAWN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return SpecialistDefinition(**json.loads(response.content[0].text.strip()))
    except Exception:
        return None


def _rewrite_prompt(
    specialist: SpecialistDefinition, rationale: str, match_query: str
) -> SpecialistDefinition:
    prompt = (
        f"Rewrite the system prompt for the '{specialist.role}' agent.\n"
        f"Critic note: {rationale}\n"
        f"Original prompt:\n{specialist.system_prompt}\n\n"
        "Return only the new system prompt text."
    )
    response = client.messages.create(
        model=settings.orchestrator_model,
        max_tokens=512,
        system="You rewrite agent system prompts to fix groupthink patterns identified by a critic.",
        messages=[{"role": "user", "content": prompt}],
    )
    return SpecialistDefinition(
        role=specialist.role,
        system_prompt=response.content[0].text.strip(),
        data_slice_id=specialist.data_slice_id,
    )
