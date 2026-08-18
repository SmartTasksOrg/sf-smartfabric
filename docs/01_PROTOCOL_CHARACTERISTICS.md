# 01 — Protocol characteristics (the conformance surface)

Every network/interop protocol is defined by a known set of *characteristics*.
This is the full list a node must fulfil to be IAIso-conformant, each with (a) the
generic requirement and (b) **how IAIso realises it**. Treat this as the master
checklist; [`06_CONFORMANCE_CHECKLIST.md`](06_CONFORMANCE_CHECKLIST.md) is its
pass/fail distillation.

> Notation: **MUST / SHOULD / MAY** per RFC 2119.

## A. Message structure

1. **Syntax** — the exact wire grammar of a message.
   *IAIso:* messages MUST serialize to the CIR envelope (see `02_FINGERPRINT.md`);
   canonical encodings are Protobuf (binary) and JSON (text), negotiated.
2. **Semantics** — what each field *means* and what actions it triggers.
   *IAIso:* semantics are defined by the **CIR verb set** (a closed, versioned list
   of operations) plus typed operands; no node may invent semantics outside a
   declared extension namespace.
3. **Encoding & charset** — byte-level representation, endianness, text encoding.
   *IAIso:* UTF-8 for text MUST; binary fields length-prefixed; endianness fixed by
   the serialization (Protobuf little-endian varints).
4. **Framing & delimitation** — where one message ends and the next begins.
   *IAIso:* length-delimited frames on stream transports; one message per unit on
   datagram/HTTP transports.

## B. Interaction & state

5. **State machine** — the legal sequence of messages (handshake → session → close).
   *IAIso:* every session follows `DISCOVER → DESCRIBE → NEGOTIATE → ADMIT →
   EXCHANGE → DRAIN → CLOSE`; illegal transitions MUST be rejected.
6. **Timing & synchronisation** — timeouts, keepalives, ordering guarantees.
   *IAIso:* declared per-profile (e.g. `at-most-once`, `ordered`, deadline in ms);
   clocks MUST be NTP/PTP-disciplined and messages timestamped.
7. **Idempotency & delivery** — at-most-once / at-least-once / exactly-once.
   *IAIso:* every command carries an idempotency key; nodes MUST declare their
   delivery guarantee in the fingerprint.

## C. Addressing & discovery

8. **Addressing** — how a peer is named and located.
   *IAIso:* a node address is `iaiso://<identity>@<placement-locator>/<capability>`;
   placement-locator encodes stack layer + region + topology (see `03`).
9. **Discovery** — how nodes find each other and their capabilities.
   *IAIso:* control-plane registry (push) + optional multicast/mDNS (pull);
   fingerprints are the discovery record.
10. **Capability negotiation** — agreeing a common profile before exchange.
    *IAIso:* intersection of both fingerprints' supported transports /
    serializations / verb-versions / QoS; if empty → no session.
11. **Versioning & compatibility** — evolving without breaking peers.
    *IAIso:* semantic version on the CIR verb set; nodes advertise a *range*;
    forward/backward compat rules are MUST-documented per verb.

## D. Reliability & flow

12. **Error handling** — a canonical error taxonomy + recovery semantics.
    *IAIso:* closed error code space (transport / auth / policy / schema / capacity /
    internal), each with a retriable flag and a machine-readable cause.
13. **Flow control** — preventing a fast sender from swamping a slow receiver.
    *IAIso:* credit-based backpressure on streams; HTTP/2 or gRPC flow control on
    those bindings.
14. **Congestion & load shedding** — behaviour under fabric-wide pressure.
    *IAIso:* nodes MUST publish a shed policy (priority classes, drop vs queue) and
    honour fabric congestion signals.
15. **Ordering & deduplication** — sequence guarantees and replay protection.
    *IAIso:* monotonic sequence per session + idempotency keys for dedupe.

## E. Security & trust

16. **Authentication** — proving identity.
    *IAIso:* mutual TLS with node certificates; workload identity via OIDC/SPIFFE
    SHOULD be supported for cloud placements.
17. **Authorization** — what an authenticated peer may do.
    *IAIso:* policy tokens (capability-scoped, short-lived) checked on every verb;
    default deny.
18. **Confidentiality & integrity** — encryption + tamper evidence in transit and
    at rest.
    *IAIso:* TLS 1.3 in transit MUST; at-rest handling declared per placement;
    payload signing for provenance.
19. **Non-repudiation & provenance** — who did what, verifiably.
    *IAIso:* every action emits a signed provenance record to the observability
    plane (mandatory — governance depends on it).
20. **Key & secret management** — rotation, custody, jurisdiction of keys.
    *IAIso:* key custody is a placement attribute (e.g. keys MUST NOT leave a
    jurisdiction); rotation policy declared in the contract.

## F. Quality, observability, governance

21. **Quality of Service** — latency/throughput/availability classes.
    *IAIso:* named QoS profiles in the fingerprint; the fabric matches producers to
    consumers by profile.
22. **Observability** — metrics, traces, logs, and their schema.
    *IAIso:* OpenTelemetry semantic conventions MUST; a trace context propagates
    across every hop.
23. **Cost & resource accounting** — attributing compute/energy/spend per action.
    *IAIso:* every action carries a resource-accounting record (tokens, time,
    energy, $), enabling per-node and per-flow costing. *(Reuse the `smartllmcost`
    model from the SmartSignal system here.)*
24. **Governance & policy** — residency, influence limits, audit, kill-switches.
    *IAIso:* policies are first-class control-plane objects; see
    [`05_DYNAMICS_AND_GOVERNANCE.md`](05_DYNAMICS_AND_GOVERNANCE.md).
25. **Extensibility** — adding capabilities without forking the protocol.
    *IAIso:* namespaced extension verbs (`x-<vendor>-<verb>`); core nodes MUST
    ignore unknown extensions gracefully.
26. **Conformance & interop testing** — a node can be *proven* compliant.
    *IAIso:* a conformance suite exercises every MUST; a node publishes its pass
    report as part of its fingerprint.

## How to use this list

- To build a **validator**: turn every MUST above into a test in the conformance
  suite. Start with A, C, E (structure, addressing, security) — they gate everything.
- To build a **node**: implement the CIR envelope + verb set + one transport +
  mTLS + OTel + provenance. That's the minimal conformant core.
- To build the **fabric**: implement the control plane (registry, negotiation,
  policy) and observability plane first; the data plane is mostly transport reuse.
