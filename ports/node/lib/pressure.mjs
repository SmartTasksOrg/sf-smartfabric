// SmartFabric — Node.js port of the IAIso pressure model.
// Independent reimplementation from the spec (docs/07 + spec/vectors), NOT a
// transpile of the Python. It must reproduce spec/vectors/pressure.vectors.json
// exactly (1e-9). That agreement is the interop proof.

export const TOLERANCE = 1e-9;

export const Zone = Object.freeze({
  NOMINAL: "nominal",
  WARNING: "warning",
  ESCALATION: "escalation",
  RELEASE: "release",
});

export const DEFAULT_CONFIG = Object.freeze({
  escalation_threshold: 0.85,
  release_threshold: 0.95,
  dissipation_per_step: 0.02,
  dissipation_per_second: 0.0,
  token_coefficient: 0.015, // per 1000 tokens
  tool_coefficient: 0.08,
  depth_coefficient: 0.05,
  post_release_lock: true,
  warning_band: 0.70,
});

function clamp(p, lo = 0.0, hi = 1.0) {
  return Math.max(lo, Math.min(hi, p));
}

export function validateConfig(c) {
  for (const name of ["escalation_threshold", "release_threshold"]) {
    const v = c[name];
    if (!(v >= 0.0 && v <= 1.0)) throw new Error(`${name}=${v} outside [0,1]`);
  }
  if (c.release_threshold <= c.escalation_threshold)
    throw new Error("release_threshold must be > escalation_threshold");
  for (const name of [
    "dissipation_per_step", "dissipation_per_second",
    "token_coefficient", "tool_coefficient", "depth_coefficient",
  ]) {
    if (c[name] < 0) throw new Error(`${name} must be >= 0`);
  }
  if (!(c.warning_band >= 0.0 && c.warning_band <= c.escalation_threshold))
    throw new Error("warning_band must be in [0, escalation_threshold]");
}

export class PressureEngine {
  constructor(config = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    validateConfig(this.config);
    this._p = 0.0;
    this._locked = false;
  }

  get pressure() { return this._p; }
  get locked() { return this._locked; }

  zone(p = this._p) {
    const c = this.config;
    if (p >= c.release_threshold) return Zone.RELEASE;
    if (p >= c.escalation_threshold) return Zone.ESCALATION;
    if (p >= c.warning_band) return Zone.WARNING;
    return Zone.NOMINAL;
  }

  step({ tokens = 0, tool_calls = 0, depth = 0, seconds = 0.0 } = {}) {
    const c = this.config;
    if (this._locked && c.post_release_lock) {
      return { pressure: this._p, zone: this.zone(), released: false, locked: true };
    }
    const intake =
      (tokens / 1000.0) * c.token_coefficient +
      tool_calls * c.tool_coefficient +
      depth * c.depth_coefficient;
    const dissipation = c.dissipation_per_step + c.dissipation_per_second * seconds;
    let p = clamp(this._p + intake - dissipation);

    if (p >= c.release_threshold - TOLERANCE) {
      this._p = 0.0;
      this._locked = c.post_release_lock;
      return { pressure: 0.0, zone: Zone.RELEASE, released: true, locked: this._locked };
    }
    this._p = p;
    return { pressure: this._p, zone: this.zone(), released: false, locked: false };
  }

  reset() { this._p = 0.0; this._locked = false; }
}

// --- fleet pressure (Layer-3 aggregation) ---------------------------------

export function fleetPressure(nodes, escalation_threshold = 0.85) {
  if (!nodes.length) return { value: 0.0, peak_node: null, peak_pressure: 0.0, hot_nodes: [] };
  const w = (n) => Math.max(n.centrality ?? 1.0, 0.0);
  const totalW = nodes.reduce((a, n) => a + w(n), 0.0) || nodes.length;
  const weighted = nodes.reduce((a, n) => a + n.pressure * w(n), 0.0) / totalW;
  const peak = nodes.reduce((m, n) => (n.pressure > m.pressure ? n : m), nodes[0]);
  const hot = nodes
    .filter((n) => n.pressure >= escalation_threshold - TOLERANCE)
    .map((n) => n.node_id)
    .sort();
  return {
    value: clamp(weighted),
    peak_node: peak.node_id,
    peak_pressure: peak.pressure,
    hot_nodes: hot,
  };
}
