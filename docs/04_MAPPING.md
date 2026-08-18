# 04 — Mapping IAIso onto infrastructure, architecture, and services

How the abstract protocol becomes real components. This is the "reference
architecture" sketch — enough to start building, not a finished design.

> **Implementation status (v0.5.0).** Part of this reference architecture now
> ships as runnable code, and part is still ahead. What exists today:
> the **node service** (CIR core + HTTP transport + verb dispatch + session
> state — `src/smartfabric/node.py`, see docs/09), **mTLS** transport
> (`src/smartfabric/mtls.py`), the **registry** (self-registration, health TTL,
> and fleet aggregation — `src/smartfabric/registry.py`), the **pressure
> aggregator** (`/fleet` on the registry + `fleet_pressure()`), the **consent
> gate** (default-deny expansion, invariant 4), the **reset coordinator** and
> **global-halt** mechanics (invariants 2 and Layer 6, in the node), and the
> **conformance service** (static `FAB-*` + behavioural vectors + live `FAB-L-*`).
> Still ahead: a **gRPC** binding (the current transport is HTTP/JSON + mTLS), a
> **highly-available** control-plane store (the registry is single-process
> in-memory today), the **negotiator** and standalone **policy/router** services,
> and the **escalation broker** as a distinct service. Those are the honest
> remaining fabric services; everything else in this doc is buildable on what
> ships now.

## 4.1 Infrastructure mapping

| IAIso concept | Concrete infrastructure |
| --- | --- |
| Control plane (registry, negotiation, policy) | a highly-available service (e.g. etcd/Consul-style store + a stateless API); or ride an existing service mesh control plane |
| Data plane transport | gRPC/HTTP-2 over mTLS; QUIC/HTTP-3 where latency matters |
| Identity | a workload-identity issuer (SPIFFE/SPIRE) or your cloud's workload identity |
| Observability plane | OpenTelemetry collector → traces/metrics/logs backend; a provenance/audit log (append-only) |
| Policy engine | OPA/Rego or a purpose-built evaluator reading control-plane policy objects |
| Fingerprint registry | the discovery record store; every node self-registers on start, deregisters on drain |

## 4.2 Architecture: the node reference shape

```
        ┌─────────────────────────────────────────┐
        │                 Node                      │
        │  ┌───────────┐   ┌──────────────────────┐ │
 native │  │  Adapter  │◄─►│  CIR core (verbs,     │ │  CIR / mTLS
surface─┼─►│ to/from   │   │  session state mach.) │◄┼───────────► fabric
        │  │  CIR      │   └───────┬──────────────┘ │
        │  └───────────┘           │                │
        │  ┌──────────────┐  ┌─────▼─────┐          │
        │  │ Policy hook  │  │ Provenance│          │
        │  │ (authz,      │  │ + cost    │──────────┼──► observability plane
        │  │  residency)  │  │ emitter   │          │
        │  └──────────────┘  └───────────┘          │
        └─────────────────────────────────────────┘
```

Five node-side components, in build order:
1. **CIR core** — envelope + verb dispatch + session state machine.
2. **Transport + mTLS** — one binding to start (gRPC).
3. **Adapter** — native ⇆ CIR (the command-level translation).
4. **Provenance + cost emitter** — OTel + signed audit + resource accounting.
5. **Policy hook** — authz + residency/influence checks before every verb.

## 4.3 Services (the fabric-side services)

| Service | Responsibility |
| --- | --- |
| **Registry** | store + serve fingerprints; health; deregistration |
| **Negotiator** | compute session profiles from two fingerprints |
| **Policy service** | distribute + evaluate governance policies |
| **Conformance service** | run the suite against a node; issue a signed pass report |
| **Router/gateway** | placement-aware routing incl. L8 residency enforcement |
| **Observability/audit** | ingest provenance + telemetry; power the dynamics layer |
| **Cost/accounting** | aggregate resource records per node/flow (reuse `smartllmcost`) |

## 4.4 Where this reuses what you already have (SmartSignal)

- **Cost/energy accounting** → the `smartllmcost` + `llm_meter` model already
  computes tokens/energy/cost per call. That *is* IAIso's resource-accounting
  record (characteristic #23). Emit it as `provenance.emit` payload.
- **The jury/council pattern** → a natural fit for the conformance service's
  judgement calls and for policy adjudication where rules are fuzzy.
- **The Atlas** → the fabric's topology (L9) is a graph; the Knowledge Atlas engine
  is already a concept-graph with centrality/physics — it can host the fabric graph
  and compute the L9 centrality/hotspot signals the dynamics layer needs.

## 4.5 Minimal viable fabric (what to build first)

1. Fingerprint schema + a validator (you already have the schema in this repo).
2. Registry + Negotiator (control plane) — the smallest useful fabric.
3. One node SDK (CIR core + gRPC + mTLS + one adapter).
4. Provenance emit + an audit log.
5. Conformance suite for characteristics A/C/E.

Everything else (QoS matching, congestion, extensions, the full dynamics layer) is
additive once those five exist.

## 4.6 IAIso fabric services (added by the core binding — see docs/07)

Beyond the generic services above, an IAIso-governed fabric runs:

| Service | Responsibility |
| --- | --- |
| **Pressure aggregator** | ingest `pressure.sample` from every node; compute `P_fleet` (topology-weighted); drive Layer-3 swarm balancing |
| **Escalation broker** | on any node entering `escalation` zone (or an invariant violation), gather the required Layer-4 authorizers before expansion continues |
| **Consent issuer** | mint + validate ConsentScope JWTs (Layer 5); the fabric's expansion gate |
| **Reset coordinator** | on a node `release`/atomic-reset, mark provenance so peers drop state derived from the wiped node (invariant 2) |
| **Global-halt controller** | Layer-6 singleton election + fleet-wide halt propagation |

These are the machine-side counterparts to the IAIso operator runtime: the operator
runtime tells the LLM how to behave; these services enforce the pressure/consent/halt
mechanics between nodes regardless of what any model "decides."
