# SwarmCast

A self-improving multi-agent swarm for World Cup match forecasting, with Polymarket edge detection and automated bet placement.

A pool of specialist agents deliberates in parallel on a match question. A holistic critic reads the full panel and identifies what the collective is missing. A Delphi round produces a confidence-weighted consensus probability. That probability is compared to the Polymarket implied price — if the spread exceeds 8 pp, SwarmCast places a limit order. Every Claude call is traced in W&B Weave and becomes a training sample for v2.

---

## Requirements

- Python 3.9+
- Node.js + `npx` (for MCP data servers)

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Environment variables

Create a `.env` file at the repo root:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
WANDB_API_KEY=...
WANDB_PROJECT=swarmcast

# WC history MCP (@zafronix/wc-mcp)
WC_API_KEY=...

# Polymarket (validation layer only — never used during deliberation)
POLYMARKET_PRIVATE_KEY=...   # Polygon wallet key for CLOB orders
```

All other values are optional and have defaults in `backend/config.py`.

---

## Data sources

Live match data is fetched at query time via two MCP servers — no static corpus, embeddings, or offline setup required:

| MCP | Provides |
|-----|---------|
| `wc26-mcp` | WC 2026 fixtures, team profiles, form, injuries, standings, H2H |
| `@zafronix/wc-mcp` | Historical WC data 1930–2026 (matches, rosters, brackets) |

Both servers are invoked automatically via `npx` on first use. Node.js must be installed.

---

## Run

```bash
uvicorn backend.main:app --reload --port 8000
```

Open `http://localhost:8000`, enter two teams, and hit **Run SwarmCast**.

---

## Project structure

```
backend/
  agents/         orchestrator, specialists, critic, delphi
  data/           wc26.py (MCP client), live.py (fallback REST)
  market/         gamma.py (Polymarket read), clob.py (order placement), edge.py
  observability/  weave_tracer.py
  main.py         FastAPI app — /forecast + /ws WebSocket
  schemas.py      Pydantic models for the full pipeline
  config.py       Settings (pydantic-settings, reads .env)
frontend/
  index.html      Match input + agent panel + consensus display
  sketch.js       p5.js Boids — fish chaos → alignment → lock
  ws.js           WebSocket client, drives phase transitions
  style.css
requirements/
  SwarmCast.md    Full system spec
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Frontend |
| `GET` | `/health` | Health check |
| `POST` | `/forecast` | Run the full swarm pipeline |
| `WS` | `/ws` | Real-time agent event stream |
