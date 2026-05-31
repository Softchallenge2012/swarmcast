"""Specialist agent runner — parallel execution via asyncio.to_thread."""
from __future__ import annotations
import asyncio
import anthropic
import weave
from ..config import settings
from ..schemas import AgentVote, SpecialistDefinition

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

VOTE_TOOL = {
    "name": "submit_vote",
    "description": "Submit your probability estimate and reasoning for the match outcome.",
    "input_schema": {
        "type": "object",
        "properties": {
            "probability":      {"type": "number", "description": "P(team A wins), 0–1"},
            "confidence":       {"type": "number", "description": "Your confidence in this estimate, 0–1"},
            "key_signal":       {"type": "string", "description": "Single most decisive factor"},
            "reasoning":        {"type": "string", "description": "Full reasoning chain (≤200 words)"},
            "uncertainty_flag": {"type": "boolean", "description": "True if data quality is low or gap is large"},
        },
        "required": ["probability", "confidence", "key_signal", "reasoning", "uncertainty_flag"],
    },
}


@weave.op()
async def run_specialist(
    specialist: SpecialistDefinition,
    context: str,
    round: int = 1,
) -> AgentVote:
    """Run one specialist agent and return its structured vote."""
    response = await asyncio.to_thread(
        client.messages.create,
        model=settings.specialist_model,
        max_tokens=1024,
        tools=[VOTE_TOOL],
        tool_choice={"type": "tool", "name": "submit_vote"},
        system=specialist.system_prompt,
        messages=[{"role": "user", "content": context}],
    )
    vote_input: dict = response.content[0].input
    return AgentVote(role=specialist.role, round=round, **vote_input)


async def run_swarm(
    specialists: list[SpecialistDefinition],
    contexts: dict[str, str],
    round: int = 1,
) -> list[AgentVote]:
    """Fire all specialists in parallel. contexts keyed by data_slice_id."""
    tasks = [
        run_specialist(s, contexts.get(s.data_slice_id, ""), round=round)
        for s in specialists
    ]
    return list(await asyncio.gather(*tasks))
