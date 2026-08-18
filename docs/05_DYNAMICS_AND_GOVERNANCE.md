# 05 — Dynamics & Governance (anchored on the IAIso pressure model)

Your earlier ask folded in AI/neurology/addiction/control and the "laws of motion"
(power law, normal distribution, chaos, randomness). With the real IAIso core in hand,
these stop being loose analogies and attach to something concrete: **the pressure
model `dp/dt`** and the fleet it runs on.

> **Framing (unchanged, and it matters):** the pressure math + layers + invariants are
> **engineering** (they're in the core). The dynamics lenses below are **measurement
> tools** on that engineering. The neurology/addiction/influence concern is a
> **governance layer** the fabric can *observe and constrain* — labelled `[hypothesis]`
> where a claim would need evidence. Keeping that line visible is what keeps the
> ambition buildable.

## 5.1 Pressure dynamics lenses (measurement on `dp/dt`)

- **Power-law / scale-free topology (S10).** In a fleet, coupling and load are
  heavy-tailed: a few high-centrality nodes dominate `P_fleet`. *Use:* weight fleet
  pressure by centrality; require that scale-free hub nodes enforce more containment
  layers and carry redundancy (a hub hitting `release` zone shouldn't take the fleet
  with it). Directly actionable — this is Layer 3 done right.
- **Normal distribution / baselining.** Per-node `p` and `dp/dt` are ~Gaussian in
  steady state. *Use:* baseline each node; a ≥Nσ jump in `dp/dt` is an early-warning
  the fabric surfaces *before* the `escalation` zone.
- **Chaos & sensitivity.** Coupled agent loops (Layer 3 swarms, Layer 3.5 regime
  shifts) can amplify. *Use:* mark loops that could run away; require damping /
  rate-limits and a determinism boundary. IAIso's clocked evaluation (invariant 3) is
  itself a chaos-control measure — it forbids continuous ungoverned loops.
  `[hypothesis: which specific fleet loops are chaotic — measure via dp/dt variance,
  don't assume.]`
- **Randomness & entropy.** Layer 1's `entropy_floor` is a real knob; entropy *source*
  quality is a substrate attribute (hardware RNG at S0). Used for crypto (ConsentScope
  signing) and any deliberate exploration jitter.

## 5.2 Influence & safety envelope (governance the fabric enforces)

IAIso already formalizes the enforceable core of this: **Layer 4** (human-in-the-loop
escalation), **Layer 5** (ConsentScope), **Layer 6** (existential guards, global halt).
The fabric extends them with an **influence class** per node so the "control / undue
influence / dependency" concern becomes a routing-and-policy fact, not a philosophy:

| Influence class | Meaning | Fabric obligation (on top of IAIso layers) |
| --- | --- | --- |
| `inert` | no user-facing behavioural effect | standard pressure telemetry |
| `informational` | presents information | provenance + source attribution |
| `persuasive` | optimises for engagement/action | influence budget (a behavioural analogue of the pressure budget); disclosure marker |
| `adaptive` | personalises via feedback loops | dependency-signal instrumentation; loop damping; Layer-4 override MUST exist |
| `autonomous` | acts without human in loop | tightest: Layer-6 kill-switch, ConsentScope on every expansion, mandatory review |

Enforceable now: influence budgets ride the *same* clocked-evaluation + escalation
machinery as pressure. When a `persuasive`/`adaptive` node exceeds its influence
budget, it trips the same Layer-4 escalation path as a pressure breach.

## 5.3 The honest boundary

- **Solid (it's in the core or trivially derived):** pressure telemetry, zones, the 5
  invariants, ConsentScope, atomic reset, power-law fleet weighting, Gaussian
  baselining, influence-class policy, loop damping. Build these.
- **Reasonable but unproven `[hypothesis]`:** that specific dependency proxies map to
  human "addiction"; that a given loop is chaotic; that an influence budget at level X
  prevents harm. Instrument them on the observability plane and let the data set the
  thresholds — exactly as IAIso says to calibrate pressure thresholds empirically.
- **Out of scope (say so):** the fabric governs *mechanisms, consent, and disclosure*,
  not minds. It never claims to read a user's neurological state.

This mirrors IAIso's own stance — *"safety through structure, not hope"*: the structure
(pressure, layers, invariants, consent) is enforced; the behavioural science is
instrumented and studied on top of it, never assumed.
