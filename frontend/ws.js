/**
 * WebSocket client — connects to /ws, drives Boids phase transitions
 * and updates the DOM as agent events arrive.
 */

const WS_URL = `ws://${location.host}/ws`;
let socket = null;

// ── DOM helpers ───────────────────────────────────────────────────────────────

function show(id)   { document.getElementById(id)?.classList.remove("hidden"); }
function hide(id)   { document.getElementById(id)?.classList.add("hidden"); }
function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }

function addAgentCard(vote) {
  const container = document.getElementById("agent-cards");
  const existing = document.getElementById(`card-${vote.role}`);
  const card = existing || document.createElement("div");
  card.id = `card-${vote.role}`;
  card.className = `agent-card${vote.round === 2 ? " round2" : ""}`;
  card.innerHTML = `
    <div class="role">${vote.role.replace(/_/g, " ")} · round ${vote.round}</div>
    <div class="prob">${(vote.probability * 100).toFixed(1)}%</div>
    <div class="signal">${vote.key_signal}</div>
    <div class="reasoning">${vote.reasoning}</div>
    ${vote.uncertainty_flag ? '<div class="flag">⚠ Low data confidence</div>' : ""}
  `;
  if (!existing) container.appendChild(card);
  updateBarChart(vote);
}

// Fallback bar chart
const barState = {};
function updateBarChart(vote) {
  barState[vote.role] = vote.probability;
  const bars = document.getElementById("bars");
  bars.innerHTML = Object.entries(barState)
    .sort(([, a], [, b]) => b - a)
    .map(([role, p]) => `
      <div class="bar-row">
        <div class="bar-role">${role.replace(/_/g, " ")}</div>
        <div class="bar-fill" style="width:${(p * 280).toFixed(0)}px"></div>
        <div class="bar-val">${(p * 100).toFixed(1)}%</div>
      </div>
    `).join("");
}

function renderCritique(critique) {
  show("critic-panel");
  document.getElementById("critic-gaps").innerHTML =
    "<strong>Coverage gaps</strong><ul>" +
    critique.coverage_gaps.map(g => `<li>${g}</li>`).join("") + "</ul>";
  document.getElementById("critic-groupthink").innerHTML =
    "<strong>Groupthink signals</strong><ul>" +
    critique.groupthink_signals.map(g => `<li>${g}</li>`).join("") + "</ul>";
  document.getElementById("critic-actions").innerHTML =
    "<strong>Actions</strong><ul>" +
    critique.recommended_actions.map(a =>
      `<li><code>${a.action}</code> — ${a.rationale}</li>`
    ).join("") + "</ul>";
}

function renderConsensus(consensus) {
  show("result-panel");
  setText("consensus-p", `${(consensus.probability * 100).toFixed(1)}%`);
  setText("consensus-ci",
    `80% CI [${(consensus.ci_low * 100).toFixed(1)}%, ${(consensus.ci_high * 100).toFixed(1)}%]`
  );
}

function renderMarket(snapshot, spread) {
  show("market-display");
  setText("market-p", `${(snapshot.market_probability * 100).toFixed(1)}%`);
  setText("spread-label", `Spread: ${(spread * 100).toFixed(1)} pp`);
}

function renderEdge(edgeDetected, betReceipt) {
  show("edge-display");
  const badge = document.getElementById("edge-badge");
  badge.className = `edge-badge ${edgeDetected ? "edge" : "no-edge"}`;
  badge.textContent = edgeDetected
    ? "EDGE DETECTED — order placed"
    : "No edge — threshold not met";
  if (betReceipt) {
    document.getElementById("bet-receipt").textContent =
      JSON.stringify(betReceipt, null, 2);
  }
}

// ── WebSocket event handler ───────────────────────────────────────────────────

function handleEvent(msg) {
  switch (msg.event) {
    case "spawning":
      window.setSwarmPhase?.("deliberating");
      break;

    case "agent_vote":
      addAgentCard(msg.payload);
      break;

    case "critic_fired":
      window.setSwarmPhase?.("critic");
      renderCritique(msg.payload);
      break;

    case "delphi_round":
      window.setSwarmPhase?.("delphi");
      addAgentCard(msg.payload);
      break;

    case "consensus":
      window.setSwarmPhase?.("consensus");
      renderConsensus(msg.payload);
      break;

    case "market_check":
      if (msg.payload.snapshot) renderMarket(msg.payload.snapshot, msg.payload.spread);
      break;

    case "edge_result":
      renderEdge(msg.payload.edge_detected, msg.payload.bet_receipt);
      break;

    case "error":
      console.error("[swarmcast]", msg.payload);
      break;
  }
}

// ── Form submit → POST /forecast ─────────────────────────────────────────────

document.getElementById("forecast-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  // Reset UI
  document.getElementById("agent-cards").innerHTML = "";
  document.getElementById("bars").innerHTML = "";
  Object.keys(barState).forEach(k => delete barState[k]);
  hide("critic-panel");
  hide("result-panel");
  hide("market-display");
  hide("edge-display");
  window.setSwarmPhase?.("deliberating");

  const teamA = document.getElementById("team-a").value.trim();
  const teamB = document.getElementById("team-b").value.trim();

  const body = {
    match_query:     `Will ${teamA} beat ${teamB}?`,
    team_a:          teamA,
    team_b:          teamB,
    team_a_id:       parseInt(document.getElementById("team-a-id").value) || 0,
    team_b_id:       parseInt(document.getElementById("team-b-id").value) || 0,
    competition_id:  document.getElementById("competition-id").value.trim() || "WC2026",
    polymarket_market_id: document.getElementById("market-id").value.trim(),
  };

  document.getElementById("run-btn").disabled = true;
  try {
    const res = await fetch("/forecast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) console.error("Forecast error", await res.text());
  } finally {
    document.getElementById("run-btn").disabled = false;
  }
});

// ── Connect WebSocket ─────────────────────────────────────────────────────────

function connect() {
  socket = new WebSocket(WS_URL);
  socket.onmessage = (ev) => {
    try { handleEvent(JSON.parse(ev.data)); } catch {}
  };
  socket.onclose = () => setTimeout(connect, 2000);
}

connect();
