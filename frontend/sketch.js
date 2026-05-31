/**
 * p5.js Boids simulation — fish chaos → alignment → lock
 *
 * Phase contract (set via window.swarmPhase):
 *   "idle"        – slow random drift
 *   "deliberating"– high chaos, random headings
 *   "critic"      – brief turbulence spike
 *   "delphi"      – partial alignment emerging
 *   "consensus"   – full lock, fish form tight cluster
 */

const BOID_COUNT = 60;
const W = 860, H = 320;

// Phase → alignment strength mapping
const PHASE_CONFIG = {
  idle:         { align: 0.02, cohesion: 0.01, separate: 0.15, speed: 1.2,  chaos: 0.8 },
  deliberating: { align: 0.04, cohesion: 0.02, separate: 0.20, speed: 2.0,  chaos: 1.4 },
  critic:       { align: 0.01, cohesion: 0.01, separate: 0.30, speed: 2.5,  chaos: 2.0 },
  delphi:       { align: 0.20, cohesion: 0.10, separate: 0.18, speed: 1.8,  chaos: 0.4 },
  consensus:    { align: 0.90, cohesion: 0.60, separate: 0.10, speed: 1.2,  chaos: 0.0 },
};

let boids = [];
let phase = "idle";

class Boid {
  constructor(p) {
    this.p = p;
    this.pos = p.createVector(p.random(W), p.random(H));
    this.vel = p5.Vector.random2D().mult(p.random(1, 2));
    this.acc = p.createVector(0, 0);
    this.maxSpeed = 3;
    this.maxForce = 0.08;
    this.hue = p.random(200, 240);
  }

  edges() {
    if (this.pos.x > W) this.pos.x = 0;
    else if (this.pos.x < 0) this.pos.x = W;
    if (this.pos.y > H) this.pos.y = 0;
    else if (this.pos.y < 0) this.pos.y = H;
  }

  flock(boids, cfg) {
    let align    = this.p.createVector();
    let cohesion = this.p.createVector();
    let separate = this.p.createVector();
    let aCount = 0, cCount = 0, sCount = 0;
    const R_ALIGN = 60, R_COHES = 100, R_SEP = 28;

    for (let other of boids) {
      if (other === this) continue;
      const d = p5.Vector.dist(this.pos, other.pos);
      if (d < R_ALIGN) { align.add(other.vel); aCount++; }
      if (d < R_COHES) { cohesion.add(other.pos); cCount++; }
      if (d < R_SEP)   {
        let diff = p5.Vector.sub(this.pos, other.pos).div(d);
        separate.add(diff); sCount++;
      }
    }

    if (aCount) { align.div(aCount).setMag(this.maxSpeed).sub(this.vel).limit(this.maxForce); }
    if (cCount) {
      cohesion.div(cCount);
      cohesion = p5.Vector.sub(cohesion, this.pos).setMag(this.maxSpeed).sub(this.vel).limit(this.maxForce);
    }
    if (sCount) { separate.div(sCount).setMag(this.maxSpeed).sub(this.vel).limit(this.maxForce); }

    this.acc.add(align.mult(cfg.align));
    this.acc.add(cohesion.mult(cfg.cohesion));
    this.acc.add(separate.mult(cfg.separate));

    // Chaos jitter
    if (cfg.chaos > 0) {
      this.acc.add(p5.Vector.random2D().mult(cfg.chaos * 0.05));
    }
  }

  update(cfg) {
    this.vel.add(this.acc).limit(this.maxSpeed * (cfg.speed / 2));
    this.pos.add(this.vel);
    this.acc.set(0, 0);
  }

  draw(p, cfg) {
    const angle = this.vel.heading();
    const alpha = this.p.map(cfg.align, 0.02, 0.9, 140, 230);
    p.push();
    p.translate(this.pos.x, this.pos.y);
    p.rotate(angle);
    p.noStroke();
    p.fill(this.hue, 180, 220, alpha);
    // Fish body
    p.ellipse(0, 0, 12, 5);
    // Tail
    p.triangle(-6, 0, -11, -4, -11, 4);
    p.pop();
  }
}

new p5((p) => {
  p.setup = () => {
    const cnv = p.createCanvas(W, H);
    cnv.parent("boids-container");
    p.colorMode(p.HSB, 360, 255, 255, 255);
    for (let i = 0; i < BOID_COUNT; i++) boids.push(new Boid(p));
  };

  p.draw = () => {
    const cfg = PHASE_CONFIG[phase] || PHASE_CONFIG.idle;
    p.background(15, 15, 25, 220);
    for (let b of boids) {
      b.flock(boids, cfg);
      b.update(cfg);
      b.edges();
      b.draw(p, cfg);
    }
  };
});

// External API — called from ws.js
window.setSwarmPhase = (newPhase) => {
  if (PHASE_CONFIG[newPhase]) {
    phase = newPhase;
    document.getElementById("phase-label").textContent = {
      idle:         "Waiting for match...",
      deliberating: "Agents deliberating independently...",
      critic:       "Holistic critic firing...",
      delphi:       "Delphi round — consensus emerging...",
      consensus:    "Consensus locked.",
    }[newPhase] || newPhase;
  }
};
