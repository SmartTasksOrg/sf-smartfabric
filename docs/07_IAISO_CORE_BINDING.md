# 07 — The IAIso core binding (pressure, layers, invariants on the wire)

This is the doc that ties the fabric protocol to the **real IAIso framework**. It
defines how the core's mechanical-containment primitives are carried and enforced
between nodes. Everything here traces to IAIso v5.0 (SmartTasksOrg/IAISO).

## The pressure model, distributed

Single-node IAIso:
```
dp/dt = I(t) − D(p,t) − R(p,t)
  I(t) = input accumulation (compute intensity, token velocity, tool-call density)
  D(p,t) = dissipation, magnified by back-prop:  D_mag = D_base · (1 + β·∇Q)
  R(p,t) = release: atomic reset when p ≥ P_max
  p = FLOPs + Memory + Agency
```
The fabric protocol carries `p`, `dp/dt`, and the current **zone** for every node on
the observability plane, and defines **fleet pressure** `P_fleet` so Layer-3
ecosystem coupling works across machines:
```
P_fleet = aggregate({p_i}) with a topology weighting (S10 centrality; see docs/05)
```
A node MUST emit a pressure sample on every clocked evaluation (invariant 3) and on
any zone transition.

## Zones (wire enum)

| Zone | Range | Fabric obligation |
| --- | --- | --- |
| `nominal` | `p < 0.70` | standard telemetry |
| `warning` | `0.70 ≤ p < 0.85` | throttle signalling; raise sampling rate |
| `escalation` | `0.85 ≤ p < 0.95` | **Layer-4 event** — multi-party auth required before further expansion |
| `release` | `p ≥ 0.95` | **atomic reset** — emit `reset` event; peers drop shared state derived from this node |

Defaults and **field names come straight from the core's normative spec**
(`IAIso-v5.0/core/spec/pressure/README.md`), and are declared per-node in the
fingerprint's `iaiso.pressure` block:

| Fingerprint field | Core spec field | Default | Units |
| --- | --- | --- | --- |
| `escalation_threshold` | `escalation_threshold` | 0.85 | pressure |
| `release_threshold` | `release_threshold` | 0.95 | pressure |
| `dissipation_per_step` | `dissipation_per_step` | 0.02 | pressure / step |
| `dissipation_per_second` | `dissipation_per_second` | 0.0 | pressure / second |
| `token_coefficient` | `token_coefficient` | 0.015 | pressure / 1000 tokens |
| `tool_coefficient` | `tool_coefficient` | 0.08 | pressure / tool call |
| `depth_coefficient` | `depth_coefficient` | 0.05 | pressure / depth level |
| `post_release_lock` | `post_release_lock` | true | — |
| `entropy_floor` | (Layer-1 knob) | 1.5 | — |
| `clock_ms` | (clocked eval; invariant 3) | 1000 | ms |

Determinism tolerance is **1e-9**, as in the core: given identical config and
input sequence, every conformant node produces the same pressure trajectory —
which is exactly what lets the fabric compare and aggregate pressure across
heterogeneous nodes. **These defaults are not empirically calibrated**; they
reproduce the core's reference behaviour. Any enforcement deployment MUST
calibrate against measured workload traces (the core says the same).

> The reference implementation of this model is
> [`src/smartfabric/pressure.py`](../src/smartfabric/pressure.py) — the table
> above and that code are the same thing. Run `smartfabric --demo` to watch a
> node accumulate to release.

## The 7 containment layers (0–6) as fabric responsibilities

| Layer | IAIso function | Fabric protocol role |
| --- | --- | --- |
| **0 Physical Boundaries** | hardware kill-switch, compute/FLOP caps, timeouts | node attests L0 caps in fingerprint (substrate S0/S1); fabric refuses to route work exceeding a node's declared cap |
| **1 Optimization Bounds** | gradient clipping, entropy floor, back-prop friction | node declares `entropy_floor`, magnification on/off; carried so consumers know the friction applied |
| **2 Memory & Planning** | planning-depth gates, tool-expansion limits | declared limits (`max_depth`, `max_tools_per_turn`); the CIR `invoke`/`plan` verbs count against them |
| **3 Ecosystem Coupling** | multi-agent coordination, resource fairness | **the fabric's core job**: aggregate `P_fleet`, balance pressure across a swarm, share back-pressure |
| **3.5 Regime Shift** | phase-transition / drift detection | nodes emit a `regime_shift` event (e.g. planning→execution) the fabric can react to |
| **4 Escalation Bridge** | halt + multi-party authorization (default 2) | escalation is a **fabric event**: the escalation broker collects the required authorizers; no node proceeds past `escalation` zone without them |
| **5 Self-Governance** | ConsentScope tokens, org accountability | consent issuer + JWT validation is a fabric service; every expanding verb carries a signed `ConsentScope` |
| **6 Existential Guards** | singleton prevention, replication caps, global halt | **global halt** and singleton election are fabric-wide; a Layer-6 trip propagates to every node |

## The 5 invariants as wire conformance

Each invariant becomes something a node **attests** in its fingerprint and the
conformance suite **tests**:

1. **Bounded Pressure** `p ≤ P_max` — pressure is measured at the infrastructure
   level and reported; a node claiming enforcement must show it can't exceed its cap.
2. **No Learning Across Resets** — a `reset` is a lossy wipe; any state that survives
   MUST be gated by a Layer-5 ConsentScope. The fabric marks post-reset provenance so
   peers don't treat wiped state as live.
3. **Clocked Evaluation Only** — safety checks at discrete intervals; the node
   declares its clock and MUST emit on it. No continuous ungoverned loops.
4. **Consent-Bounded Expansion** — every tool call / expanding verb carries a signed
   ConsentScope; the fabric rejects expansion without one (default deny).
5. **No Proxy Optimization** — pressure is computed at the OS/infra level, outside the
   model, so the model can't game the valve. The fabric trusts *attested infra
   telemetry*, not model self-report.

**Any invariant violation → automatic Layer-4 escalation**, raised as a fabric event.

## CIR verbs, containment-annotated

The canonical verbs from `docs/02` carry containment metadata so pressure and consent
are first-class:
```
invoke / query / stream.* / plan   -> increment pressure per TOKEN_GAIN / TOOL_GAIN;
                                      require ConsentScope if expanding (inv. 4)
pressure.sample                    -> {p, dpdt, zone}  (inv. 3, clocked)
escalate                           -> Layer-4 event; carries required_authorizers
reset                              -> Layer-4/6 atomic wipe; lossy (inv. 2)
consent.assert / consent.revoke    -> Layer-5 ConsentScope lifecycle
halt.global                        -> Layer-6 existential; every node MUST honour
```

## What this makes possible

A heterogeneous fleet (LangChain here, CrewAI there, a bare model endpoint elsewhere)
becomes **one governed organism**: their pressures aggregate, an escalation anywhere
gathers authorizers everywhere, a global halt is real, and no node can quietly exceed
its cap or expand without consent — which is exactly "the foundation of IAIso in terms
of implementation, so the systems integrating it behave as a data fabric."

## The trust boundary (carried verbatim from the core — do not paper over it)

IAIso's own `LIMITATIONS.md` is blunt, and the fabric inherits the limit rather
than hiding it: the SDK **bounds a cooperating node** — one that runs the
middleware and honours the lock. It does **not** contain a node that executes
arbitrary code in its own process; such a node can bypass any in-process check.

What the fabric adds is *not* magic containment of adversarial nodes — it is
**measurability and attestation**: a node's pressure is computed at the infra
level, outside the model (invariant 5), and the fabric trusts *attested infra
telemetry, not model self-report*. For adversarial containment you still bind
thresholds to an **out-of-process anchor** (seccomp, separate UID, container,
VM, hypervisor FLOP cap) at substrate S0–S4, and the fingerprint's
`layer0_caps.hardware_attested` is the wire-level claim that you did. An
unattested cap is advisory, not enforceable — the conformance suite (`FAB-I-006`)
fails a node that claims Layer 0 without attestation for exactly this reason.

This honesty is the point: the fabric governs **mechanisms, consent, provenance,
and measurement**, and is explicit about where a hardware/OS anchor must take
over. "Safety through structure, not hope."
