"""Wire format — canonical JSON encoding + length-delimited framing.

This is the *frozen* interop baseline. Two conformant implementations, in any
language, MUST produce byte-identical output for the same CIR message. That is
what turns IFP from an architecture into a protocol: the bytes are pinned, not
just the concepts.

Two serializations are defined by IFP:

  * **Canonical JSON** (this module) — the MUST-interop baseline. Deterministic,
    language-neutral, hashable. Every conformant node MUST implement it.
  * **Protobuf** (``proto/fabric.proto``) — the binary contract with frozen field
    numbers, for high-throughput data-plane use. A node MAY implement it; field
    numbers never change.

Canonical JSON rules (normative — see docs/08_WIRE_FORMAT.md):
  1. UTF-8, no BOM.
  2. Object keys sorted ascending by Unicode code point.
  3. No insignificant whitespace: item separator ``,``, key separator ``:``.
  4. Absent optional fields are *omitted*, never emitted as ``null``.
  5. Integers are bare (no leading zeros, no ``+``, no exponent).
  6. Envelope fields carry no floats — telemetry numbers live in payloads and are
     compared numerically (1e-9), not byte-wise, so canonical JSON stays stable
     across language float formatters.

Framing: unsigned LEB128 varint length prefix, then that many payload bytes. One
message per frame; a stream is a concatenation of frames.
"""
from __future__ import annotations

import json
from typing import Any

from .models import CIRHeader, CIRMessage, CIRPolicy, InfluenceClass

WIRE_VERSION = "0.2"


# --------------------------------------------------------------------------- #
# Canonical JSON                                                              #
# --------------------------------------------------------------------------- #

def canonical_json(obj: Any) -> bytes:
    """Serialize to the canonical JSON byte string (see rules above)."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def envelope_to_canonical(msg: CIRMessage) -> dict[str, Any]:
    """Project a CIRMessage into its canonical dict form (rule 4: omit absent)."""
    h = msg.header
    header = _drop_none(
        {
            "id": h.id,
            "verb": h.verb,
            "verb_version": h.verb_version,
            "from": h.from_addr,
            "to": h.to_addr,
            "idempotency": h.idempotency,
            "trace": h.trace,
            "deadline_ms": h.deadline_ms,
            "qos_profile": h.qos_profile,
        }
    )
    ic = msg.policy.influence_class
    policy = _drop_none(
        {
            "residency": msg.policy.residency,
            "influence_class": ic.value if isinstance(ic, InfluenceClass) else ic,
            "audit_required": msg.policy.audit_required,
        }
    )
    out: dict[str, Any] = {"header": header, "policy": policy}
    if msg.auth:
        out["auth"] = msg.auth
    if msg.body:
        out["body"] = msg.body
    if msg.meta:
        out["meta"] = msg.meta
    return out


def encode(msg: CIRMessage) -> bytes:
    """CIRMessage -> canonical JSON bytes."""
    return canonical_json(envelope_to_canonical(msg))


def decode(data: bytes | str | dict[str, Any]) -> CIRMessage:
    """Canonical JSON (bytes/str) or a dict -> CIRMessage."""
    if isinstance(data, (bytes, str)):
        obj = json.loads(data)
    else:
        obj = data
    h = obj["header"]
    p = obj.get("policy", {})
    ic = p.get("influence_class")
    return CIRMessage(
        header=CIRHeader(
            id=h["id"],
            verb=h["verb"],
            from_addr=h["from"],
            to_addr=h["to"],
            verb_version=h.get("verb_version", "0.1"),
            idempotency=h.get("idempotency"),
            trace=h.get("trace"),
            deadline_ms=h.get("deadline_ms"),
            qos_profile=h.get("qos_profile"),
        ),
        body=obj.get("body", {}),
        auth=obj.get("auth", {}),
        policy=CIRPolicy(
            residency=p.get("residency"),
            influence_class=InfluenceClass(ic) if ic else None,
            audit_required=p.get("audit_required", True),
        ),
        meta=obj.get("meta", {}),
    )


# --------------------------------------------------------------------------- #
# LEB128 varint framing                                                       #
# --------------------------------------------------------------------------- #

def write_varint(n: int) -> bytes:
    if n < 0:
        raise ValueError("varint length must be non-negative")
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def read_varint(buf: bytes, offset: int = 0) -> tuple[int, int]:
    """Return (value, new_offset). Raises on truncation."""
    result = 0
    shift = 0
    pos = offset
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")


def frame(payload: bytes) -> bytes:
    """Length-delimit a single payload: varint(len) || payload."""
    return write_varint(len(payload)) + payload


def deframe(buf: bytes, offset: int = 0) -> tuple[bytes, int]:
    """Read one frame at ``offset``. Return (payload, new_offset)."""
    length, pos = read_varint(buf, offset)
    end = pos + length
    if end > len(buf):
        raise ValueError("frame length exceeds buffer")
    return buf[pos:end], end


def frame_message(msg: CIRMessage) -> bytes:
    """CIRMessage -> framed canonical-JSON bytes ready for a stream transport."""
    return frame(encode(msg))
