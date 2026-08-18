"""Wire objects: the CIR envelope, the closed verb set, and the enums a node
declares in its fingerprint.

The CIR (Canonical Intermediate Representation) is the neutral command form
every node translates *to* and *from*. Two nodes never learn each other's
native dialects — only the CIR. That keeps fabric interop at O(n) adapters
instead of O(n²) integrations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InfluenceClass(str, Enum):
    """Substrate S10 governance dimension — how a node affects behaviour.

    Drives the fabric's *influence budget* (docs/05): persuasive/adaptive nodes
    ride the same escalation machinery as pressure when they exceed budget.
    """

    INERT = "inert"
    INFORMATIONAL = "informational"
    PERSUASIVE = "persuasive"
    ADAPTIVE = "adaptive"
    AUTONOMOUS = "autonomous"


# The closed, versioned CIR verb set. A node may only implement verbs from this
# list (plus namespaced ``x-<ns>-<verb>`` extensions). Semantics are fixed here
# so pressure and consent can be first-class per verb (see docs/07 §CIR verbs).
CIR_VERBS: dict[str, str] = {
    "describe": "return this node's fingerprint",
    "negotiate": "agree a session profile",
    "invoke": "call a capability (request/response); may expand pressure",
    "query": "read data/state",
    "stream.open": "open a streaming exchange",
    "stream.data": "streaming payload frame",
    "stream.close": "close a streaming exchange",
    "subscribe": "pub/sub subscription",
    "event": "pub/sub event delivery",
    "plan": "declare planning depth; counts against Layer-2 depth limits",
    "pressure.sample": "emit {p, dpdt, zone} on the clock (invariant 3)",
    "escalate": "raise a Layer-4 escalation (carries required_authorizers)",
    "reset": "Layer-4/6 atomic wipe; lossy (invariant 2)",
    "consent.assert": "present a Layer-5 ConsentScope for an expanding verb",
    "consent.revoke": "revoke a ConsentScope by jti",
    "policy.get": "read a governance policy",
    "policy.assert": "assert a governance decision",
    "provenance.emit": "mandatory signed audit record",
    "halt.global": "Layer-6 existential halt; every node MUST honour",
}

# Verbs that expand an agent's reach and therefore REQUIRE a ConsentScope
# (invariant 4: consent-bounded expansion). Default deny without one.
EXPANDING_VERBS: frozenset[str] = frozenset({"invoke", "plan", "stream.open"})


def is_extension_verb(verb: str) -> bool:
    return verb.startswith("x-")


def is_known_verb(verb: str) -> bool:
    return verb in CIR_VERBS or is_extension_verb(verb)


@dataclass
class CIRHeader:
    id: str                       # ULID
    verb: str                     # a CIR verb
    from_addr: str                # iaiso:// address
    to_addr: str                  # iaiso:// address
    verb_version: str = "0.1"
    idempotency: str | None = None
    trace: str | None = None      # W3C traceparent
    deadline_ms: int | None = None
    qos_profile: str | None = None


@dataclass
class CIRPolicy:
    residency: str | None = None
    influence_class: InfluenceClass | None = None
    audit_required: bool = True


@dataclass
class CIRMessage:
    """The CIR envelope. ``policy`` and the containment metadata are what make
    pressure/consent first-class rather than bolted on."""

    header: CIRHeader
    body: dict[str, Any] = field(default_factory=dict)   # {schema_ref, payload}
    auth: dict[str, Any] = field(default_factory=dict)   # {token, sig}
    policy: CIRPolicy = field(default_factory=CIRPolicy)
    meta: dict[str, Any] = field(default_factory=dict)   # {placement_hint, cost_hint}

    def requires_consent(self) -> bool:
        """True if this verb expands reach and so needs a ConsentScope (inv. 4)."""
        return self.header.verb in EXPANDING_VERBS

    def has_consent(self) -> bool:
        return bool(self.auth.get("token"))
