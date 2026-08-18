# 06 — Conformance checklist (pass/fail)

A node is **IAIso-fabric-conformant** when every MUST below passes. The conformance
service runs these and issues a signed report the node includes in its fingerprint.

## This checklist is executable

Every check below has a stable **`FAB-*` ID** (the fabric's analogue of the
family's `PREFIX-*` rule IDs — SmartPangolin's `SEC-*`, SmartSeal's `SEAL-*`).
The reference suite in [`src/smartfabric/conformance.py`](../src/smartfabric/conformance.py)
runs them against a fingerprint and emits a report validating against
[`schema/conformance-report.schema.json`](../schema/conformance-report.schema.json):

```bash
smartfabric conformance schema/example.fingerprint.json          # human-readable
smartfabric conformance schema/example.fingerprint.json --json   # the signed report
```

| Check ID | Level | What it verifies |
| --- | --- | --- |
| `FAB-C-001` | MUST | schema-valid fingerprint |
| `FAB-C-002` | MUST | every port fully declared (port hygiene) |
| `FAB-C-003` | MUST | only known CIR verbs; `describe` present |
| `FAB-C-004` | MUST | command-translation mapping targets known verbs |
| `FAB-C-005` | MUST | mTLS + TLS 1.3 declared |
| `FAB-C-006` | MUST | OpenTelemetry + provenance declared |
| `FAB-C-007` | MUST | resolvable `iaiso://` address w/ placement locator |
| `FAB-I-001` | MUST | publishes an `iaiso` containment posture |
| `FAB-I-002` | MUST | pressure config present + core-consistent |
| `FAB-I-003` | MUST | declares a clocked-evaluation interval (inv. 3) |
| `FAB-I-004` | MUST | consent issuer present when scope required (inv. 4) |
| `FAB-I-005` | MUST | reset declared lossy (inv. 2) |
| `FAB-I-006` | MUST | Layer-0 caps hardware-attested if Layer 0 enforced |
| `FAB-G-001` | SHOULD | jurisdiction + egress posture declared |
| `FAB-G-002` | SHOULD | adaptive/autonomous nodes expose override/kill-switch |
| `FAB-G-003` | SHOULD | resource-accounting / cost standard declared |

> **Scope of the reference suite (be honest about it):** the `FAB-*` checks are
> *static* — they verify what a node **declares** (fingerprint completeness,
> internal consistency, posture-binding). **Behavioural** conformance is a
> separate, runnable contract: the vectors in
> [`spec/vectors/`](../spec/vectors/) pin inputs → outputs, and an implementation
> is behaviourally conformant iff it reproduces every one. Run both:
>
> ```bash
> smartfabric conformance schema/example.fingerprint.json   # static FAB-*
> smartfabric vectors                                        # behavioural vectors
> ports/conformance/run.sh                                   # BOTH impls, must agree
> ```

## Two independent implementations (the protocol bar)

A protocol is only a protocol when **two independent implementations interoperate
on the same wire**. IFP meets that bar today: the Python reference
([`src/smartfabric/`](../src/smartfabric/)) and an independent Node port
([`ports/node/`](../ports/node/)) both pass the identical `spec/vectors/*.json` —
including **byte-exact** canonical-JSON and framing agreement (see
[`docs/08_WIRE_FORMAT.md`](08_WIRE_FORMAT.md)). `ports/conformance/run.sh` is the
gate. A third implementation is conformant the moment it passes the same vectors,
with no coordination required.

The prose checklist below is the full surface the two layers of testing target.

## IAIso containment conformance (MUST — this is what binds to the core; see docs/07)
- [ ] Publishes an `iaiso` posture block (framework_version, enforced_layers, pressure config)
- [ ] Emits `pressure.sample` {p, dpdt, zone} on its declared clock (invariant 3)
- [ ] Enforces zone semantics: escalation ≥0.85 gathers Layer-4 authorizers; release ≥0.95 atomic-resets
- [ ] **Bounded Pressure** (inv. 1): cannot exceed declared `P_max`; measured at infra level
- [ ] **No Learning Across Resets** (inv. 2): reset is lossy; surviving state is ConsentScope-gated
- [ ] **Clocked Evaluation Only** (inv. 3): no continuous ungoverned loops
- [ ] **Consent-Bounded Expansion** (inv. 4): every expanding verb carries a signed ConsentScope
- [ ] **No Proxy Optimization** (inv. 5): pressure computed outside the model; fabric trusts attested infra, not self-report
- [ ] Honours a fabric `halt.global` (Layer 6) and propagates escalation events
- [ ] Layer-0 caps are hardware-attested (substrate S0/S1) if `enforced_layers` includes 0

## Core protocol conformance (MUST)
_Grouped by the characteristics in `01`._

## Core (MUST — a node is non-conformant without all of these)
- [ ] Publishes a schema-valid fingerprint (`schema/fingerprint.schema.json`)
- [ ] Declares every port it opens; opens no undeclared port
- [ ] Serializes to the CIR envelope (Protobuf or JSON)
- [ ] Implements the closed CIR verb set it advertises, at the advertised versions
- [ ] Enforces the session state machine; rejects illegal transitions
- [ ] Carries an idempotency key on every command; declares its delivery guarantee
- [ ] Resolves and honours `iaiso://` addresses incl. placement locator
- [ ] Negotiates a profile before exchange; refuses on empty intersection
- [ ] mTLS with a valid node certificate
- [ ] Default-deny authorization; checks a policy token per verb
- [ ] TLS 1.3 in transit
- [ ] Emits a signed provenance record for every action
- [ ] Emits OpenTelemetry traces/metrics/logs with propagated trace context
- [ ] Emits a resource-accounting record (tokens/time/energy/$) per action
- [ ] Returns errors only from the closed error taxonomy, with retriable flags
- [ ] Publishes its placement vector (L0–L10 as applicable)

## Placement & governance (MUST where applicable)
- [ ] Declares jurisdiction (L8) and egress posture; honours residency contracts
- [ ] Declares influence class (L10); enforces its obligations
- [ ] `adaptive`/`autonomous` nodes expose a working human-override + kill-switch
- [ ] Key custody honours jurisdiction constraints
- [ ] Bottom-up trust: claimed trust level supported by L0/L1/L4 attributes

## Quality (SHOULD)
- [ ] Publishes QoS profiles and matches by them
- [ ] Implements flow control + a declared load-shed policy
- [ ] Supports versioning ranges with documented compat rules
- [ ] Ignores unknown `x-*` extensions gracefully

## Dynamics instrumentation (SHOULD; enables the governance layer)
- [ ] Feedback loops are provenance-instrumented end to end
- [ ] Exposes metrics sufficient for centrality (L9) and anomaly baselining
- [ ] `persuasive`/`adaptive` nodes honour influence budgets + disclosure markers

## Report format
```json
{
  "node": "iaiso://acme-model-7@cn.bj.az2/...",
  "suite_version": "0.1.0",
  "ran_at": "2026-08-17T00:00:00Z",
  "results": { "core": "pass", "governance": "pass", "quality": "partial" },
  "failures": [],
  "signature": "ed25519:..."
}
```
