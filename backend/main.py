"""FastAPI app — /forecast endpoint + /ws WebSocket for real-time agent state."""
from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import settings
from .schemas import ForecastResult, WSEventType, WSMessage
from .observability import weave_tracer
from .agents.orchestrator import spawn_specialists, act_on_critique
from .agents.specialists import run_swarm
from .agents.critic import run_critic
from .agents.delphi import aggregate, run_delphi_round
from .data.live import build_context_bundle
from .data.rag import query as rag_query
from .market.gamma import find_wc_market
from .market.edge import detect_and_act


@asynccontextmanager
async def lifespan(app: FastAPI):
    weave_tracer.init()
    yield


app = FastAPI(title="SwarmCast", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, msg: WSMessage):
        data = msg.model_dump_json()
        for ws in list(self._connections):
            try:
                await ws.send_text(data)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


# ── Request / response models ─────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    match_query: str               # e.g. "Will Brazil beat France?"
    team_a: str
    team_b: str
    team_a_id: int
    team_b_id: int
    competition_id: str            # e.g. "WC2026"
    polymarket_market_id: str = "" # optional override; auto-discovered if empty


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_pipeline(req: ForecastRequest) -> ForecastResult:
    async def emit(event: WSEventType, payload):
        await manager.broadcast(WSMessage(event=event, payload=payload))

    # Layer 0 — RAG seed
    rag_chunks = rag_query(req.match_query)
    rag_context = "\n\n".join(rag_chunks)

    # Layer 0 — live data
    contexts = build_context_bundle(
        req.team_a_id, req.team_b_id,
        req.team_a, req.team_b,
        req.competition_id,
    )
    contexts["statsbomb"] = rag_context  # inject RAG into tactical slice

    # Layer 1 — meta-orchestrator spawns specialists
    specialists = spawn_specialists(req.match_query)
    await emit(WSEventType.spawning, [s.model_dump() for s in specialists])

    # Layer 2 — round 1 swarm
    round1_votes = await run_swarm(specialists, contexts, round=1)
    for v in round1_votes:
        await emit(WSEventType.agent_vote, v.model_dump())

    # Layer 3 — holistic critic
    critique = run_critic(round1_votes, req.match_query)
    await emit(WSEventType.critic_fired, critique.model_dump())

    # Orchestrator acts on critique (spawn / rewrite / broadcast)
    specialists = act_on_critique(critique, specialists, req.match_query)

    # Layer 4 — Delphi round 2
    round2_votes = await run_delphi_round(specialists, round1_votes, contexts)
    for v in round2_votes:
        await emit(WSEventType.delphi_round, v.model_dump())

    consensus = aggregate(round2_votes)
    await emit(WSEventType.consensus, consensus.model_dump())

    # Layer 6 — Polymarket (first and only contact)
    market_id = req.polymarket_market_id or find_wc_market(req.team_a, req.team_b) or ""
    snapshot, spread, edge_detected, bet_receipt = (None, None, False, None)
    if market_id:
        snapshot, spread, edge_detected, bet_receipt = detect_and_act(
            consensus.probability, market_id
        )
        await emit(WSEventType.market_check, {
            "snapshot": snapshot.model_dump() if snapshot else None,
            "spread": spread,
        })
        await emit(WSEventType.edge_result, {
            "edge_detected": edge_detected,
            "bet_receipt": bet_receipt.model_dump() if bet_receipt else None,
        })

    return ForecastResult(
        match_query=req.match_query,
        consensus=consensus,
        critique=critique,
        market=snapshot,
        spread=spread,
        edge_detected=edge_detected,
        bet_receipt=bet_receipt,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/forecast", response_model=ForecastResult)
async def forecast(req: ForecastRequest):
    return await run_pipeline(req)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()   # keep connection alive; pipeline pushes to client
    except WebSocketDisconnect:
        manager.disconnect(ws)
