# 00 — Overview: IAIso as a data fabric

## The one-sentence model

> A **data fabric** is a set of nodes that all publish the same kind of contract,
> so the fabric — not bespoke integration code — handles **discovery, description,
> addressing, translation, transport, and governance** between any two of them.

IAIso makes AI components (models, tools, agents, stores, sensors, gateways) and
the systems that host them into fabric nodes by giving each one:

1. an **identity** (who/what it is, cryptographically),
2. a **fingerprint** (what it speaks, on what ports, with what commands),
3. a **placement** (where it sits in the stack, geo, and topology),
4. a **contract** (the guarantees it makes and the policies that bind it).

If a node publishes all four in IAIso form and passes conformance, it drops into
the fabric and interoperates with everything else that did.

## Core concepts and vocabulary

| Term | Meaning |
| --- | --- |
| **Node** | Any addressable participant: a model endpoint, tool, agent, store, gateway, or a whole subsystem exposed as one. |
| **Fingerprint** | The machine-readable descriptor a node publishes (ports, standards, commands, placement, contract). The unit of interop. |
| **CIR** (Canonical Intermediate Representation) | The neutral command/data form every node translates *to* and *from*. Two nodes never need to understand each other directly — only the CIR. |
| **Adapter** | The translation shim between a node's native surface and the CIR (command-level translation). |
| **Placement** | Where a node is: stack layer, region, jurisdiction, topological position. |
| **Contract** | The guarantees (latency, availability, determinism, data-handling) and the policies (residency, influence limits, audit) a node is bound by. |
| **Fabric plane** | Three logical planes: **data** (payloads move), **control** (discovery, negotiation, policy), **observability** (telemetry, audit, provenance). |

## The three planes

- **Data plane** — moves payloads between nodes using negotiated transport +
  serialization. Optimized for throughput/latency.
- **Control plane** — discovery, capability negotiation, addressing, admission,
  and policy distribution. This is where fingerprints are registered and matched.
- **Observability plane** — every action emits provenance and telemetry so the
  fabric can be audited, costed, and governed (this is where the dynamics/governance
  layer plugs in).

## Design invariants (non-negotiables)

1. **Contract before connection** — no node talks to another before both
   fingerprints are read and a compatible profile is negotiated.
2. **Translate through the CIR, never peer-to-peer dialects** — O(n) adapters, not
   O(n²) integrations.
3. **Placement is first-class** — where a node is (silicon → jurisdiction →
   topology) is part of its addressable identity, not an afterthought.
4. **Everything is observable and attributable** — no silent actions; provenance is
   mandatory, because governance depends on it.
5. **Fail closed on policy, fail open on discovery** — unknown nodes are
   discoverable but get zero trust until they prove conformance.

> **Binding to the IAIso core:** this overview describes the generic fabric. The
> concrete pressure model, containment layers 0–6, and 5 invariants that the
> fabric carries and enforces are specified in [`07_IAISO_CORE_BINDING.md`](07_IAISO_CORE_BINDING.md).
