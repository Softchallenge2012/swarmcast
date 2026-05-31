# SwarmCast
### A Self-Improving Multi-Agent Swarm for World Cup Match Forecasting
*with Polymarket Edge Detection and Automated Bet Placement*

> "Feed it a World Cup match. A swarm of specialist agents deliberates in isolation, a holistic critic finds what the collective is blind to, and a Delphi consensus emerges — then the swarm bets against the market if it disagrees. Every call logged. Every bet traced. Every resolved match a training sample."

*Multi-Agent Orchestration Hackathon · MIT / The Engine, Cambridge MA · May 31, 2026 · #BosTechWeek*

---

## 0. Forecast Question

```python
MATCH_HOME = "<home team>"
MATCH_AWAY = "<away team>"

QUESTION = (
    f"Predict the final score for {MATCH_HOME} vs {MATCH_AWAY} in a World Cup match. "
    "Provide goals for each team and a confidence score between 0.0 and 1.0."
)
```

The `QUESTION` string is the single input to the pipeline. The meta-orchestrator receives it verbatim and uses it to spawn the specialist pool. All agent prompts are derived from this question — no other match context is pre-injected by the caller.

---

## 1. The Core Idea

SwarmCast is a multi-agent deliberation system for World Cup match forecasting. A meta-orchestrator reads the match and spawns a pool of specialist agents — each with a narrow analytical lens and a scoped data slice. Agents deliberate in parallel without seeing each other's outputs. A holistic critic reads the full panel as a unified picture and identifies what the collective intelligence is missing. A Delphi voting round gives specialists one revision pass. A confidence-weighted consensus probability emerges.

The consensus probability is then compared to the Polymarket implied price on the same match — fetched for the first time only after the vote is sealed. If the divergence exceeds the edge threshold (default: 8 percentage points), SwarmCast places a limit order on the CLOB API.

Every deliberation step is traced in W&B Weave. When the match resolves, traces are labeled with the ground truth outcome — building the training dataset for v2 Serverless RL fine-tuning on CoreWeave.

### Why This Is Interesting

- **Genuine independent deliberation** — agents never see the market price or each other's reasoning during round 1. The probability is SwarmCast's own, not an anchored derivative of the crowd.
- **Holistic adversarial critique** — the critic reads the full panel as a unified picture and identifies what the collective intelligence is missing about this specific match. It does not antagonize individual agents for the sake of it. The challenge is question-specific, not agent-specific.
- **Anthropic SDK as the orchestration backbone** — Claude Sonnet 4 runs all specialist agents and the meta-orchestrator via tool use for structured output. Claude Haiku 4.5 runs the holistic critic fast and cheap. Voyage-3 handles embeddings. One coherent provider story: Anthropic reasons, CoreWeave runs, Weave watches.
- **Falsifiable claim** — the output is a probability with a confidence interval, a minority dissent report, and an explicit spread against the market. Judges can verify it in June.
- **Weave-instrumented from day one** — every agent call is a future training sample. The v2 retraining story is already embedded in the v1 architecture.
- **CoreWeave timing** — the platform that enables the v2 training loop was announced two days before the hackathon. SwarmCast is the proof of concept for that platform story.

---

## 2. System Architecture

### 2.1 Layers Overview

| Layer | Name | Description |
|-------|------|-------------|
| 0 | RAG Seed | Retrieves football-only context: static Kaggle corpus via cosine similarity + live squad, form, injury data. Polymarket explicitly excluded. |
| 1 | Meta-Orchestrator | Claude Sonnet 4 reads the match, writes specialist system prompts dynamically, spawns the agent pool. |
| 2 | Specialist Swarm | N agents in parallel on Claude Sonnet 4, full isolation, scoped context. Each emits `{ probability, confidence, key_signal, reasoning, uncertainty_flag }`. |
| 3 | Holistic Critic | Claude Haiku 4.5 reads the full panel as one document. Returns a system-level critique: `coverage_gaps`, `groupthink_signals`, `recommended_actions`. Does NOT challenge agents individually. |
| 4 | Delphi Vote | Specialists see aggregate P distribution (no reasoning chains), submit final vote. Confidence-weighted consensus P + 80% CI + minority dissent computed. |
| 5 | Weave Observability | Cross-cutting. Every agent call traced throughout: role, prompt version, P emitted, reasoning, round 1 vs round 2 delta. |
| 6 | Polymarket Validation | **First and only contact with Polymarket.** Gamma API fetches market P. Edge detector: `\|SwarmCast P − market P\|`. If > 8%: CLOB API places limit order. |
| 7 | Visualization | p5.js Boids fish simulation via WebSocket. Fish chaos → alignment → lock mirrors deliberation state. |
| 8 | Output | Consensus P + CI + minority dissent + spread vs market + bet receipt or no-edge flag. |

### 2.2 Model Architecture

| Role | Model | Purpose |
|------|-------|---------|
| Meta-orchestrator | Claude Sonnet 4 (Anthropic API) | Reads match, writes specialist prompts dynamically, parses critic output, decides spawn/rewrite/broadcast actions. |
| Specialist agents | Claude Sonnet 4 (Anthropic API) | All 5–6 specialists. Structured output via tool use — vote schema defined as a tool, Claude fills it. `asyncio.to_thread` for parallel execution. |
| Holistic critic | Claude Haiku 4.5 (Anthropic API) | Fast, cheap system-level auditor. Reads full panel as one document. Returns single critique document. Does NOT address individual agents. |
| Embedding model | Voyage-3 (voyageai, Anthropic-recommended) | Embeds static Kaggle corpus offline. Cosine similarity via numpy at query time — no vector DB for v1. |

### 2.3 Specialist Agent Pool — World Cup Edition

For "Will [Team A] beat [Team B]?", the meta-agent spawns:

- **Tactical Analyst** — StatsBomb xG, PPDA, formation, possession stats. Assesses structural tactical advantages.
- **Historical Stats Agent** — Kaggle WC history 1930–2022, H2H record, win rate by stage and confederation matchup. Computes base rates.
- **Current Form Agent** — Last 5 results, goals scored/conceded, W/D/L sequence. Assesses momentum trajectory.
- **Squad Fitness Agent** — Transfermarkt injury list, suspensions, squad depth. Assesses lineup quality delta vs full-strength.
- **Tournament Context Agent** — Group standings, qualification scenarios, rest days, venue, climate. Assesses strategic incentives affecting lineup or intensity.
- **Contrarian Agent** — Structurally biased against the favourite. Surfaces the strongest underdog case.

### 2.4 Holistic Critic Design

The critic is a system-level auditor, not a debate coach. It receives the full panel output as one unified document — all agent roles, probabilities, confidence scores, key signals, and reasoning chains concatenated — and is instructed:

> *"You are a system-level auditor. Read this panel output as a whole. Do not comment on individual agents. Identify what the collective analysis is missing about this specific question. Return a structured critique with: `coverage_gaps` (list), `groupthink_signals` (list), `recommended_actions` (spawn | rewrite | broadcast, with rationale)."*

The orchestrator then acts:
- **spawn** — creates new specialist agents for identified coverage gaps
- **rewrite** — updates system prompts for agents exhibiting groupthink
- **broadcast** — sends the gap signal as an addendum to all specialists before the Delphi round

The critic never directly addresses any agent. Its output goes to the orchestrator only.

### 2.5 Anthropic SDK Orchestration Pattern

All LLM calls use the Anthropic Python SDK. `asyncio.to_thread` wraps the synchronous client for parallel specialist execution:

```python
import anthropic
import asyncio

client = anthropic.Anthropic()

VOTE_TOOL = {
    "name": "submit_vote",
    "description": "Submit your probability estimate and reasoning",
    "input_schema": {
        "type": "object",
        "properties": {
            "probability": {"type": "number"},
            "confidence": {"type": "number"},
            "key_signal": {"type": "string"},
            "reasoning": {"type": "string"},
            "uncertainty_flag": {"type": "boolean"}
        },
        "required": ["probability", "confidence", "key_signal", "reasoning", "uncertainty_flag"]
    }
}

async def run_specialist(system_prompt: str, context: str) -> dict:
    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        tools=[VOTE_TOOL],
        tool_choice={"type": "tool", "name": "submit_vote"},
        system=system_prompt,
        messages=[{"role": "user", "content": context}]
    )
    return response.content[0].input  # tool use returns structured dict

async def run_swarm(specialists: list[dict]) -> list[dict]:
    return await asyncio.gather(*[
        run_specialist(**s) for s in specialists
    ])
```

The meta-orchestrator is prompted to return a JSON array of specialist definitions at runtime — each with `role`, `system_prompt`, and `data_slice_id`. Dynamic spawning: the orchestrator writes the agents' instructions based on the specific match question.

---

## 3. Data Sources

> **Critical constraint:** No source that publishes betting odds, prediction market prices, or bookmaker lines is permitted in the deliberation layer.

### Static — embed offline tonight

| Source | Provides | Feeds |
|--------|----------|-------|
| `piterfm/fifa-world-cup` (Kaggle) | Every WC match 1930–2022. Base rates by team, stage, confederation. | Historical stats |
| `harrachimustapha/fifa-world-cup-team-dataset` (Kaggle) | Team features 2002–2026. FIFA rankings, squad value, avg age. | Historical stats |
| `areezvisram12/wc2026-match-data` (Kaggle, SQLite) | 2026 schedule, venues, groups, confirmed squads. | Orchestrator |
| StatsBomb Open Data (GitHub, free) | Event-level xG, passes, pressures. WC 2018 + 2022. Tactical fingerprints. | Tactical analyst |

### Live — fetch at query time

| Source | Provides | Feeds |
|--------|----------|-------|
| `football-data.org` (free, API key) | Fixtures, standings, squad lists, last 5 results. 10 req/min. | Form + squad |
| Transfermarkt (transfermarkt-scraper) | Injuries, suspensions, squad depth. Only free source for current injury status. | Squad fitness |
| API-Football (free, 100 req/day) | H2H records, lineups, coach stats. Backup H2H source. | Historical stats |

### Validation only — fetched after vote is sealed

| Source | Provides | Role |
|--------|----------|------|
| Polymarket Gamma API (no auth) | Market implied P, 24h volume, open interest. | Edge detector |
| Polymarket CLOB API (wallet auth, Polygon USDC) | Order placement if spread > threshold. Limit orders only. | Bet executor |

### RAG implementation — no vector DB needed

Embed the static corpus (~500 docs) with Voyage-3 tonight. Save as numpy array + metadata list. At query time: embed the match query, cosine similarity, return top 10 chunks. Live API responses go directly into specialist prompts as structured JSON. Polymarket is never queried during this phase.

---

## 4. Tech Stack

| Component | Choice |
|-----------|--------|
| LLM orchestration | Anthropic Python SDK — Claude Sonnet 4 (orchestrator + specialists), Haiku 4.5 (critic) |
| Structured output | Anthropic tool use — vote schema as tool, `tool_choice` forced |
| Embeddings | Voyage-3 via `voyageai` Python package |
| GPU infrastructure | CoreWeave — low-latency parallel inference |
| Backend | FastAPI + WebSockets |
| Visualization | p5.js Boids (OpenProcessing starter) |
| Observability | W&B Weave — every Anthropic API call traced |
| Data fetching | httpx (async), cached for demo duration |
| Betting | `py-clob-client` (Polymarket Python SDK), Polygon wallet |
| Deployment | CoreWeave VM + ngrok |

---

## 5. Context Engineering

Non-negotiable principles:

- **Narrow role definition** — each prompt states explicitly what to analyze and what *not* to consider. Scope enforcement prevents any agent from solving the whole problem.
- **Data slice injection** — only the relevant data is injected per agent. No agent sees the full dataset. Clean structured JSON only — no raw HTML or unformatted API responses.
- **Independence instruction** — every prompt includes: *"Form your own independent view based solely on your assigned data. Do not speculate about what other analysts might conclude."*
- **Market blindness** — no agent prompt references Polymarket, betting odds, or market-implied probability. Enforced at prompt construction level.
- **Sparse Delphi signal** — agents see only the aggregate P distribution in the Delphi round, not reasoning chains. Prevents anchoring, preserves pool diversity.
- **Output schema enforcement** — tool use forces structured output. Reasoning is a field within the schema, not the response format.

---

## 6. Build Order

> Total: ~8 hours. Step 1 is a hard gate — do not proceed until it passes.

1. **(30 min)** Verify CoreWeave access. Successful inference call to Claude Sonnet 4 and Haiku 4.5.
2. **(30 min)** Embed static Kaggle corpus with Voyage-3. Confirm cosine similarity returns sensible chunks.
3. **(1 hr)** Build meta-agent spawner. Hardcode fallback specialist list for test match.
4. **(1 hr)** Write all 6 specialist prompts. Test each individually. Confirm tool use output.
5. **(1 hr)** Build aggregation + Delphi layer. End-to-end: match in → parallel agents → weighted P out.
6. **(1 hr)** Build holistic critic. Confirm it produces a system-level critique, not per-agent challenges.

> **🥗 LUNCH CHECKPOINT** — working deliberation pipeline with holistic critique. Minimum viable demo.

7. **(30 min)** Wire W&B Weave tracing. Confirm traces appear in dashboard.
8. **(30 min)** Connect Polymarket Gamma API post-vote. Compute spread. Confirm edge detection.
9. **(30 min)** Connect CLOB API. Place one test limit order to confirm wallet + auth.
10. **(1 hr)** Build p5.js Boids visualization. Get it running client-side with hardcoded params.
11. **(30 min)** Add FastAPI WebSocket. Connect visualization to backend.
12. **(30 min)** Rehearse demo script twice with a fresh match. Time it.

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| CoreWeave latency too high | Pre-cache one full run on demo match. Show live run; cut to cache if it stalls. |
| Holistic critic too agreeable | Strengthen system prompt: *"If you cannot find a gap, look harder. A panel that agrees on everything is always missing something."* |
| Polymarket has no liquid WC match market | Group stage starts June 11. Fall back to pre-tournament winner markets ($517M volume, live today). |
| CLOB API wallet/auth fails | Decouple bet execution from demo narrative. Show edge detection + would-be order. Spread calculation is the key moment. |
| Fish visualization not ready | Fallback: live probability bar chart showing agent votes updating in real time. Build this first. |
| Critic loop produces no change | Floor: critic always recommends spawning contrarian if none present. Even one spawn makes self-improvement legible. |
| WiFi unreliable | Mobile hotspot. Run backend locally with ngrok tunnel. |

---

## 8. Demo Script — 3 Minutes

**0:00 — Hook (15s)**
*"Polymarket has a live market on tonight's World Cup match. The crowd says 64%. We disagree. Let me show you why."*

**0:15 — Spawn (20s)**
Show meta-agent spawning specialists. *"No human told it to create a squad fitness agent. It figured out which experts it needs from the match alone."*

**0:35 — Deliberation (30s)**
Fish appear, swimming chaotically. *"Each fish is an agent forming an independent opinion. They have never seen the market price. Watch them disagree."*

**1:05 — Holistic critic fires (25s)**
Show critic output. *"Now Claude Haiku reads the full panel as one picture. Not to argue with each fish — to find what the whole school is blind to. It flagged that no agent covered tournament context: both teams need to win, not draw. That changes everything."*

**1:30 — Delphi + consensus (20s)**
Fish begin aligning. *"After the Delphi round, the swarm says 71%. The market says 64%. The spread is 7 points."*

**1:50 — Edge + bet (20s)**
*"Our threshold is 8%. We're at 7 — no bet. But if that contrarian agent had held firm, we'd be placing an order right now on Polygon."* Show would-be CLOB order.

**2:10 — Weave + Anthropic (20s)**
Show Weave dashboard. *"Every Claude call is traced — Sonnet for the specialists, Haiku for the critic. When the match resolves, these traces get ground truth labels. That is the retraining dataset. CoreWeave announced this loop two days ago. We built the proof of concept today, on Anthropic."*

**2:30 — Close (30s)**
Fish lock into final formation. *"No central coordinator told these agents what to conclude. The probability came from specialization, isolation, and a critic that looked at the whole picture. The fish are not decorative — they are the system. Check back in June."*

---

## 9. Pitch Deck — Team Recruitment

### Slide 1 — The Hook

> **The World Cup starts in 12 days.**
> Polymarket has live match markets.
> **What if an agent swarm could find the edge?**

*Say this out loud. Pause after "find the edge?" Let it land.*

---

### Slide 2 — What SwarmCast Does

- Specialist agents deliberate on a World Cup match in parallel — tactical, historical, form, fitness, contrarian
- A holistic critic (Claude Haiku 4.5) reads the full panel as one picture — not to antagonize each agent, but to find what the collective is blind to about this match
- The orchestrator acts: spawns agents for coverage gaps, rewrites prompts for groupthink, broadcasts gap signals before the Delphi round
- Delphi consensus vote → calibrated probability with CI and minority dissent
- Polymarket price fetched for the **first time AFTER** the vote is sealed
- If spread > 8%: SwarmCast places a limit order automatically on Polygon
- Every Claude call traced in W&B Weave → ground truth on resolution → v2 training data

> *The swarm never sees the market price until it has already voted. **That is what makes the edge real.***

---

### Slide 3 — Why Now

CoreWeave announced their agentic AI platform **two days ago** — a closed loop between inference, observability, and retraining using W&B Weave and Serverless RL.

SwarmCast instruments that exact loop from day one. When markets resolve, Weave traces become training samples. V2 fine-tunes specialists on what reasoning patterns predicted correctly.

We are not demoing a concept. We are building the proof of concept for their platform story — **the day the World Cup starts.**

| 20 active WC markets today | $517M winner market volume | 3 models, distinct roles |
|---|---|---|

---

### Slide 4 — The Stack

| Component | Detail |
|-----------|--------|
| Anthropic SDK | Claude Sonnet 4 (specialists + orchestrator) · Haiku 4.5 (critic) · Voyage-3 (embeddings) |
| W&B Weave | Every agent call traced · bet events logged · ground truth labeled on resolution |
| Polymarket APIs | Gamma API (read-only) + CLOB API (order placement, wallet auth) |
| Football data | Kaggle WC datasets (static) + football-data.org + Transfermarkt (live) |
| Python + asyncio | `asyncio.gather` fires all specialists in parallel · httpx for data fetching |
| FastAPI + WebSockets | Backend API + real-time agent state push |
| p5.js Boids | Fish visualization · chaos → alignment → lock |

---

### Slide 5 — The Ask

> **Looking for 2–3 people. 8 hours. Three tracks.**

| Python / async | Frontend / p5.js | LLM / prompts |
|---|---|---|
| Agent orchestration, data fetch, aggregation, CLOB integration | Boids visualization, WebSocket integration, FastAPI frontend | Specialist prompts, critic design, tool use schemas, Weave tracing |

**Minimum viable demo by lunch. Bet placed by end of day.**

---

## The One-Liner

*SwarmCast: a self-improving agent swarm built on Claude that deliberates on World Cup matches, bets against the market when it disagrees, and gets smarter every time a match resolves.*
