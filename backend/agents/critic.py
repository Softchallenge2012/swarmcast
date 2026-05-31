"""Holistic critic — reads the full panel as one document, never addresses agents individually."""
from __future__ import annotations
import json
import anthropic
import weave
from ..config import settings
from ..schemas import AgentVote, CritiqueOutput, RecommendedAction, CriticAction

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

CRITIC_SYSTEM = """\
You are a system-level auditor for a multi-agent forecasting panel.
You receive the full panel output as a single unified document.

Rules:
- Do NOT comment on individual agents by name.
- Do NOT antagonize agents for the sake of debate.
- Identify what the COLLECTIVE analysis is missing about this SPECIFIC match question.
- If you cannot find a gap, look harder. A panel that agrees on everything is always missing something.
- The contrarian agent counts as coverage only if it raised a genuinely distinct mechanism.

Return a JSON object with exactly these fields:
  "coverage_gaps":        list of strings — topics/factors the panel did not address
  "groupthink_signals":   list of strings — patterns where agents converged without independent evidence
  "recommended_actions":  list of objects with fields:
      "action":      "spawn" | "rewrite" | "broadcast"
      "rationale":   string
      "target_role": string or null  (required for "rewrite", null for others)

Return ONLY the JSON object. No prose, no markdown fences.
"""

CRITIC_TOOL = {
    "name": "submit_critique",
    "description": "Submit the system-level critique of the full agent panel.",
    "input_schema": {
        "type": "object",
        "properties": {
            "coverage_gaps":       {"type": "array", "items": {"type": "string"}},
            "groupthink_signals":  {"type": "array", "items": {"type": "string"}},
            "recommended_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action":      {"type": "string", "enum": ["spawn", "rewrite", "broadcast"]},
                        "rationale":   {"type": "string"},
                        "target_role": {"type": ["string", "null"]},
                    },
                    "required": ["action", "rationale"],
                },
            },
        },
        "required": ["coverage_gaps", "groupthink_signals", "recommended_actions"],
    },
}


def _format_panel(votes: list[AgentVote]) -> str:
    lines = []
    for v in votes:
        lines.append(
            f"[{v.role.upper()}] P={v.probability:.2f} conf={v.confidence:.2f} "
            f"flag={v.uncertainty_flag}\n"
            f"Key signal: {v.key_signal}\n"
            f"Reasoning: {v.reasoning}\n"
        )
    return "\n---\n".join(lines)


@weave.op()
def run_critic(votes: list[AgentVote], match_query: str) -> CritiqueOutput:
    """Run the holistic critic over the full agent panel."""
    panel_doc = f"Match question: {match_query}\n\n" + _format_panel(votes)

    response = client.messages.create(
        model=settings.critic_model,
        max_tokens=1024,
        tools=[CRITIC_TOOL],
        tool_choice={"type": "tool", "name": "submit_critique"},
        system=CRITIC_SYSTEM,
        messages=[{"role": "user", "content": panel_doc}],
    )
    raw: dict = response.content[0].input
    actions = [
        RecommendedAction(
            action=CriticAction(a["action"]),
            rationale=a["rationale"],
            target_role=a.get("target_role"),
        )
        for a in raw.get("recommended_actions", [])
    ]
    return CritiqueOutput(
        coverage_gaps=raw.get("coverage_gaps", []),
        groupthink_signals=raw.get("groupthink_signals", []),
        recommended_actions=actions,
    )
