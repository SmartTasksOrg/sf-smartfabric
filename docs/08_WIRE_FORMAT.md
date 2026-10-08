# 08 — Wire format (frozen)

This is the byte-level contract. Everything above it (fingerprint, CIR verbs,
pressure semantics) is only interoperable because the bytes are pinned here. Two
conformant implementations MUST produce identical output for the same message;
`ports/conformance/run.sh` proves it across Python and Node today.

> Notation: **MUST / SHOULD / MAY** per RFC 2119. `wire_version: 0.2`.

## 8.1 Two serializations, one meaning

| Serialization | Status | Use |
| --- | --- | --- |
| **Canonical JSON** (§8.2) | **MUST** implement | interop baseline; control plane; anything hashed, signed, or logged |
| **Protobuf** (`proto/fabric.proto`, §8.4) | **MAY** implement | high-throughput data plane; field numbers frozen |

A node negotiates serialization via its fingerprint `standards.serialization`.
Canonical JSON is the floor every node shares, so a session can always fall back
to it. A message means the same thing in either encoding.

## 8.2 Canonical JSON (normative)

The canonical form exists so that a message has **exactly one** byte
representation — required for stable hashing, signing (provenance, invariant 5),
and cross-language equality. The rules:

1. **Encoding** — UTF-8, no BOM.
2. **Object key order** — keys sorted ascending by Unicode code point.
3. **Whitespace** — none that is insignificant. Item separator is `,`, key/value
   separator is `:`. No spaces, no newlines.
4. **Absent optionals are omitted** — a field with no value is not present. It is
   never emitted as `null`. (This is what keeps two encoders agreeing without a
   shared "which fields are null" convention.)
5. **Integers** — bare: no leading zeros, no leading `+`, no exponent.
6. **No floats in envelope fields** — every envelope field is a string, integer,
   boolean, or nested object. Floating-point telemetry (pressure `p`, `dpdt`)
   travels inside a typed `body.payload` and is compared **numerically** (1e-9),
   never by canonical-byte equality — so JSON float-formatting differences across
   languages can never break envelope interop.
7. **Strings** — standard JSON string escaping (RFC 8259).

The reference encoder is [`src/sf_smartfabric/wire.py`](../src/sf_smartfabric/wire.py)
(`encode`/`decode`); the independent Node encoder is
[`ports/node/lib/wire.mjs`](../ports/node/lib/wire.mjs). Both are checked
byte-for-byte against `spec/vectors/envelope.vectors.json`.

### The envelope shape

```
CIRMessage {
  header {                          // required
    id            // ULID           (required)
    verb          // CIR verb       (required)
    verb_version  // semver         (required)
    from, to      // iaiso://       (required)
    idempotency   // string         (optional)
    trace         // W3C traceparent(optional)
    deadline_ms   // integer        (optional)
    qos_profile   // string         (optional)
  }
  policy {                          // required
    audit_required // bool          (default true)
    residency      // string        (optional)
    influence_class// enum          (optional)
  }
  auth  { token, sig }              // optional (present for expanding verbs — inv. 4)
  body  { schema_ref, payload }     // optional; payload typed by schema_ref
  meta  { placement_hint, cost_hint}// optional
}
```

## 8.3 Framing (normative)

On stream transports a message is length-delimited:

```
frame := varint(len(payload)) || payload
```

- `varint` is unsigned **LEB128** (7 bits/byte, high bit = continuation).
- `payload` is the canonical-JSON bytes (§8.2) or the Protobuf bytes (§8.4).
- A stream is a concatenation of frames; a reader reads one varint, then that
  many bytes, and repeats.
- On datagram/HTTP transports, one message per unit; no framing prefix.

Reference: `frame` / `deframe` in `wire.py`; `frame` / `readVarint` in
`wire.mjs`. `envelope.vectors.json` pins `framed_hex` for each message, so the
framing is interop-tested, not just described.

## 8.4 Protobuf (frozen field numbers)

`proto/fabric.proto` is the binary contract. **Field numbers are permanent** —
they are never reused or renumbered; removed fields become `reserved`; new fields
append with new numbers. This is standard Protobuf forward/backward-compat
discipline and is what lets a v0.3 node talk to a v0.2 node.

The closed CIR verb set is the `Verb` enum with frozen numbers; an extension verb
travels in `CIRHeader.ext_verb` with `verb == VERB_UNSPECIFIED`.

Binary interop is not exercised by the harness in this repo (no `protoc` in the
build sandbox); the field-number freeze + the canonical-JSON equivalence are the
guarantees a Protobuf implementation binds to. Wiring a `protoc`-generated
round-trip vector is tracked in `private/roadmap`.

## 8.5 Versioning & compatibility (normative)

- **`wire_version`** (this doc) governs the envelope + framing. It bumps only on a
  breaking change to encoding rules.
- **`verb_version`** (per message) is the semver of the CIR verb's semantics. A
  node advertises a supported **range** per verb in its fingerprint; negotiation
  intersects ranges (docs/01 §11).
- **Canonical-JSON rule 4 (omit absent)** means adding a new optional field is
  backward-compatible: old readers ignore unknown keys, new readers treat a
  missing key as absent.
- **Protobuf field-number freeze** gives the same property on the binary side.

A change that would alter the bytes for an existing message (reorder keys, emit a
previously-omitted field, renumber a proto field) is **breaking** and MUST bump
`wire_version`. The vectors are the tripwire: any such change diffs
`spec/vectors/*.json` in CI.
