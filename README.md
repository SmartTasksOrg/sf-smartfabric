<!-- mcp-name: io.github.smarttasksorg/smartfabric · part of the Smart* family -->
<h1 align="center">🦔 SmartFabric</h1>
<p align="center"><b>Carry IAIso containment across the whole fleet. One wire protocol, one node fingerprint — so many governed AI agents behave as one governed data fabric, not a pile of independently-wrapped agents.</b></p>
<p align="center">
  <a href="https://iaiso.org">IAIso §0 · Fabric</a> ·
  <a href="https://github.com/SmartTasksOrg/IAISO/tree/main/IAIso-v5.0/core">binds to IAIso v5.0 core</a> ·
  <a href="https://smarttasks.cloud">SmartTasks.cloud</a> ·
  <a href="#part-of-the-smart-family">the Smart* family</a>
</p>

---

## The problem: AI is spreading through your systems, and you can't see the layer it lives on

AI/LLM calls now sit inside your CRM, your CI, your data pipelines, your agents.
Each one influences and controls real systems — and each is wired in its own
bespoke way. There is no common layer where you can **measure, monitor, audit,
and trace** what the AI is doing across all of it. You can't govern a black box,
and you certainly can't govern a hundred differently-shaped black boxes.

**SmartFabric** is the hardened layer that separates AI/LLM traffic and
functionality out into its own governed plane. It is the reference
implementation of the **IAIso Fabric Protocol (IFP)**: a wire protocol + a node
**fingerprint** that every AI node publishes, so a heterogeneous fleet becomes
measurable and enforceable as one organism.

Where the [IAIso engine](https://github.com/SmartTasksOrg/IAISO) answers *"is
**this** agent over pressure?"*, IFP answers *"what is the pressure of the
**whole system**, is any node about to breach, and can a global halt be honoured
everywhere at once?"* — the questions IAIso's Layer 3 (ecosystem coupling),
Layer 4 (escalation) and Layer 6 (existential guards) can only answer if nodes
speak a common protocol.

```bash
pip install smartfabric
smartfabric --demo        # offline tour: pressure → fleet → conformance
```

## What it does, in one screen

`smartfabric --demo` runs three things against bundled synthetic data, no network:

1. **Single-node pressure** — drives a token/tool workload up the `dp/dt` curve
   until it hits the release threshold and atomically resets (invariant 2:
   lossy, no learning across resets).
2. **Fleet pressure** — aggregates five nodes into one topology-weighted
   `P_fleet` (Layer-3), so a high-centrality hub moves the number more than a leaf.
3. **Conformance** — runs the `FAB-*` suite over an example fingerprint and
   prints a pass/fail report a node can carry in its own contract.

## Run it in your stack

| Where you work | How you run it |
|---|---|
| **Python** | `pip install smartfabric` |
| **CLI (validate)** | `smartfabric validate <fp.json>` · `conformance <fp.json>` · `fleet <fleet.json>` |
| **CLI (run a node)** | `smartfabric serve` runs a node · `smartfabric registry` runs the fleet registry · `smartfabric live` runs the `FAB-L-*` harness |
| **Behavioural proof** | `smartfabric vectors` runs the pinned interop vectors; `ports/conformance/run.sh` runs them across Python + Node + Java |
| **Other languages** | independent ports in [`ports/`](ports/) (Node, Java runnable; Go, PHP, Rust shipped). The protocol is defined by `spec/vectors/*.json` — reproduce them and you're conformant |

## What's in this repo

- **The spec** — [`docs/`](docs/), reading order below. `docs/07` is the binding
  to the real IAIso v5.0 core (pressure fields, layers 0–6, the 5 invariants);
  `docs/08` is the frozen wire format.
- **The contract** — [`schema/fingerprint.schema.json`](schema/fingerprint.schema.json):
  the machine-readable descriptor every node publishes, plus a passing
  [`example.fingerprint.json`](schema/example.fingerprint.json).
- **A runnable reference** — [`src/smartfabric/`](src/smartfabric/): the pressure
  engine, fleet aggregation, CIR envelope + wire codec, the `FAB-*` conformance
  suite, a live HTTP/CIR **node** (`node.py`) with optional **mTLS** (`mtls.py`),
  an over-the-wire harness (`live.py`), and a **registry** (`registry.py`) for
  fleet discovery + `P_fleet` aggregation. Deterministic, offline, dependency-light.
- **Independent ports** — [`ports/`](ports/): Node + Java (runnable, in CI) and Go,
  PHP, Rust (shipped, vector-checked). Interop harness in `ports/conformance/`.
- **Toolchain integrations** — [`integrations/`](integrations/): LangChain, n8n,
  Flowise, and a GitHub Action that gate/meter agents through a fabric node.
- **Deployments** — [`deploy/`](deploy/): Dockerfile, a two-node compose fabric,
  and GCP/AWS/Azure recipes for the node service.
- **Conformance vectors** — [`spec/vectors/`](spec/vectors/): pinned input→output
  cases (pressure, fleet, envelope) that define the protocol independently of code.
- **Family metadata** — [`spec/iaiso-map.json`](spec/iaiso-map.json), `.smart.json`.
- **Tests** — [`tests/`](tests/): the public suite (59 green), including the live
  node harness.

## Reading order

| Doc | What it covers |
| --- | --- |
| [`docs/00_OVERVIEW.md`](docs/00_OVERVIEW.md) | Fabric model, the three planes, how it wraps the core |
| [`docs/07_IAISO_CORE_BINDING.md`](docs/07_IAISO_CORE_BINDING.md) | **The binding: pressure model, layers 0–6, the 5 invariants, and the trust boundary** |
| [`docs/01_PROTOCOL_CHARACTERISTICS.md`](docs/01_PROTOCOL_CHARACTERISTICS.md) | The full conformance surface (26 characteristics) |
| [`docs/02_FINGERPRINT.md`](docs/02_FINGERPRINT.md) | Ports, standards, command-translation (CIR) + containment posture |
| [`docs/03_SUBSTRATE_AND_LAYERS.md`](docs/03_SUBSTRATE_AND_LAYERS.md) | Two axes: containment layers 0–6 × physical substrate S0–S10 |
| [`docs/04_MAPPING.md`](docs/04_MAPPING.md) | Fabric services: pressure aggregator, escalation broker, consent issuer |
| [`docs/05_DYNAMICS_AND_GOVERNANCE.md`](docs/05_DYNAMICS_AND_GOVERNANCE.md) | Pressure dynamics + influence governance, with the honest boundary |
| [`docs/06_CONFORMANCE_CHECKLIST.md`](docs/06_CONFORMANCE_CHECKLIST.md) | The executable `FAB-*` static suite + the behavioural-vector / two-implementation bar |
| [`docs/08_WIRE_FORMAT.md`](docs/08_WIRE_FORMAT.md) | **The frozen wire format: canonical JSON, framing, Protobuf, versioning** |
| [`docs/09_TRANSPORT_AND_OPERATIONS.md`](docs/09_TRANSPORT_AND_OPERATIONS.md) | **Running the system: the node service, mTLS, live `FAB-L` conformance, the registry** |
| [`docs/10_DEPLOYMENT.md`](docs/10_DEPLOYMENT.md) | **Deploying it: one image, the full platform matrix incl. k8s/Helm and GPU providers** |

## How it works (the honest version)

The IAIso trust boundary is inherited, not hidden: IFP **bounds cooperating
nodes** and makes them *measurable and attestable*. Pressure is computed at the
infrastructure level, outside the model (invariant 5), so a node can't game its
own valve, and the fabric trusts *attested infra telemetry, not model
self-report*. For **adversarial** containment you still bind thresholds to an
out-of-process anchor (seccomp / container / VM / hypervisor FLOP cap) at
substrate S0–S4 — and `layer0_caps.hardware_attested` is the wire-level claim
that you did. `FAB-I-006` fails any node that claims Layer 0 without it. Safety
through structure, not hope.

Rule/check IDs are namespaced `FAB-*` so output looks kin to the rest of the
family (SmartPangolin's `SEC-*`, SmartSeal's `SEAL-*`).

## Part of the Smart* family

SmartFabric is the **fabric layer** of IAIso — the plane the other tools ride on.
It stacks naturally with [SmartSeal](https://github.com/SmartTasksOrg/smartseal) (provenance
records on the observability plane), [SmartRoute](https://github.com/SmartTasksOrg/smartroute)
(trust-gated routing), and [SmartLLMCost](https://github.com/SmartTasksOrg/smartllmcost) (the
resource-accounting record — characteristic #23). Everything conforms to the open
**[IAIso standard](https://github.com/SmartTasksOrg/IAISO)** and bundles in
**[SmartTasks.cloud](https://smarttasks.cloud)**.

## Status

`v0.2.0 — protocol` (was a draft at v0.1). Grounded on IAIso v5.0. The three
things that separate a draft from a protocol are now in place and enforced by
running code:

- **A frozen wire format** — canonical-JSON encoding + LEB128 framing, and a
  field-number-frozen `proto/fabric.proto`. See [`docs/08_WIRE_FORMAT.md`](docs/08_WIRE_FORMAT.md).
- **Two independent implementations that interoperate** — the Python reference
  and an independent Node port ([`ports/node/`](ports/node/)) both pass the same
  vectors, byte-for-byte. `ports/conformance/run.sh` is the gate.
- **Behavioural conformance** — [`spec/vectors/`](spec/vectors/) pins inputs →
  outputs; `smartfabric vectors` runs them. Static `FAB-*` checks remain for what
  a node *declares*.

Still honest about what's next: a live network harness against a running node,
run Protobuf binary interop (field numbers are frozen; not exercised here without
`protoc`), and ed25519 report signing. See `CHANGELOG.md`.

## Contact

Companies wanting hands-on integration of the fabric into their architecture,
audit-ready: **[enterprise@smarttasks.cloud](mailto:enterprise@smarttasks.cloud)**.

