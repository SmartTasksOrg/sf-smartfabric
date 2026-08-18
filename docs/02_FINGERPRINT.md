# 02 — The Fingerprint: ports, standards, command-level translation

A node's **fingerprint** is the single machine-readable descriptor it publishes.
It is what discovery returns, what negotiation reads, and what the conformance
suite validates. The authoritative shape is
[`schema/fingerprint.schema.json`](../schema/fingerprint.schema.json); this doc
explains the three interop-critical sections.

## 2.1 Ports (what it listens/speaks on)

IAIso follows IANA port practice and makes port usage explicit and auditable:

- **Well-known (0–1023)** — only for standard bindings a node re-uses (e.g. 443 for
  HTTPS/gRPC-over-TLS). Declared, never assumed.
- **Registered (1024–49151)** — IAIso reserves a *documented* default per binding
  in this range (pick one for your deployment and record it in `ports[]`).
- **Dynamic/ephemeral (49152–65535)** — for negotiated data-plane channels.

Each port entry MUST declare: `number`, `transport` (tcp/udp/quic/unix),
`binding` (grpc/http2/http3/ws/raw), `tls` (required/optional/none), `plane`
(data/control/observability), and `direction` (listen/dial/both). A node that
opens an undeclared port is **non-conformant** — the fingerprint is a contract, and
port hygiene is part of it (this is also how the fabric does security posture).

## 2.2 Standards (what it speaks)

The fingerprint lists the standards a node implements, grouped by concern, so
negotiation can compute the intersection. Minimum categories:

| Concern | Examples a node might declare |
| --- | --- |
| Transport | `tcp`, `quic`, `http/2`, `http/3`, `grpc`, `websocket` |
| Serialization | `protobuf`, `json`, `cbor`, `arrow`, `msgpack` |
| Identity/Auth | `mtls`, `oidc`, `spiffe`, `jwt` |
| Crypto | `tls1.3`, `ed25519`, `aes-256-gcm` |
| Schema/typing | `json-schema`, `protobuf3`, `avro` |
| Observability | `otel-traces`, `otel-metrics`, `otel-logs` |
| Domain (AI) | `openai-chat`, `mcp`, `openinference`, `<your model API>` |
| Governance | `iaiso-policy/1`, `residency/1`, `provenance/1` |

Negotiation succeeds only where both nodes share at least one option in each
*required* concern.

## 2.3 Command-level translation (the CIR)

This is the heart of the fabric. Nodes never learn each other's native command
dialects; each node ships an **adapter** that maps its native surface **to and from
the Canonical Intermediate Representation (CIR)**. Interop cost is O(n) adapters,
not O(n²) integrations.

### The CIR envelope (conceptual)

```
CIRMessage {
  header {
    id            // ULID
    idempotency   // key
    trace         // W3C traceparent
    from, to      // iaiso:// addresses
    verb          // CIR verb, e.g. "invoke", "query", "stream.open"
    verb_version  // semver
    deadline_ms
    qos_profile
  }
  auth   { token, sig }
  body   { schema_ref, payload }   // payload typed by schema_ref
  policy { residency, influence_class, audit_required }
  meta   { placement_hint, cost_hint }
}
```

### The CIR verb set (closed, versioned — starter list)

| Verb | Meaning |
| --- | --- |
| `describe` | return this node's fingerprint |
| `negotiate` | agree a session profile |
| `invoke` | call a capability, request/response |
| `query` | read data/state |
| `stream.open` / `stream.data` / `stream.close` | streaming exchange |
| `subscribe` / `event` | pub/sub |
| `policy.get` / `policy.assert` | governance |
| `provenance.emit` | mandatory audit record |
| `x-<ns>-<verb>` | namespaced extension |

### Adapter contract

An adapter MUST provide two pure functions:

```
to_cir(native_request)   -> CIRMessage
from_cir(CIRMessage)     -> native_request        # inbound
to_native(CIRMessage)    -> native_response        # and the reverse pair
from_native(native_response) -> CIRMessage
```

and MUST declare, in the fingerprint, the **mapping table**: `native_command →
cir_verb (+ field map)`. That table is the "command-level translation" — it is
inspectable, testable, and versioned. Example row:

```
{ "native": "POST /v1/chat/completions",
  "cir_verb": "invoke",
  "capability": "text.generate",
  "field_map": { "messages": "body.payload.messages",
                 "temperature": "body.payload.params.temperature" } }
```

## 2.4 Why fingerprint everything

Because the fabric's guarantees are only as strong as its ability to *know* each
node: ports gate security posture, standards gate interop, the CIR mapping gates
translation, and placement (next doc) gates governance. A node that under-declares
is a hole in the fabric; conformance testing exists to close it.

---

## 2.5 IAIso containment posture (the part that binds to the core)

Beyond ports/standards/CIR, an IAIso-governed node MUST publish its **containment
posture** — this is what makes the fabric able to enforce the core (see `docs/07`).

```jsonc
"iaiso": {
  "framework_version": "5.0",
  "enforced_layers": [0, 1, 2, 4, 5],        // which containment layers 0-6 this node enforces
  "pressure": {                               // field names mirror the core spec exactly
    "escalation_threshold": 0.85,             // Layer-4 escalation band
    "release_threshold": 0.95,                // atomic reset
    "dissipation_per_step": 0.02,
    "dissipation_per_second": 0.0,
    "token_coefficient": 0.015,               // pressure per 1000 tokens
    "tool_coefficient": 0.08,                 // per tool call
    "depth_coefficient": 0.05,                // per planning-depth level
    "post_release_lock": true,
    "entropy_floor": 1.5,                     // Layer 1
    "backprop_magnification": true,
    "clock_ms": 1000                          // clocked evaluation interval (invariant 3)
  },
  "layer0_caps": { "max_flops": 1e13, "timeout_ms": 30000, "hardware_attested": true },
  "consent": { "issuer": "https://consent.example.org", "algo": "ed25519", "scope_required": true },
  "reset": { "lossy": true, "consent_gated_persistence": true },   // invariant 2
  "invariants_attested": [1, 2, 3, 4, 5],     // which of the 5 invariants a conformance run verified
  "multi_party_auth": 2                        // Layer 4 default authorizers
}
```

- **enforced_layers** lets a consumer refuse a node that doesn't enforce a layer its
  flow requires (e.g. a high-risk task needs Layer 6).
- **pressure** carries the core's actual config so telemetry is interpretable and
  `P_fleet` is computable.
- **layer0_caps.hardware_attested** ties to substrate S0/S1 — an unattested cap is
  advisory, not enforceable.
- **invariants_attested** is the wire-level statement of the 5 invariants a
  conformance run checked (see `docs/06`).

A node that omits the `iaiso` block is treated as **ungoverned**: discoverable, but
the fabric grants it zero expansion trust and routes no governed flow to it.
