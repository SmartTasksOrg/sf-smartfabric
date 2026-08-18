"""Fingerprint: load, schema-validate, and read an IAIso node descriptor.

The fingerprint is the single machine-readable contract a node publishes —
what discovery returns, what negotiation reads, and what conformance validates.
A node that under-declares is a hole in the fabric; this module is how the hole
gets found.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

try:  # jsonschema is a hard dep of the package, but keep import errors legible
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore


_ADDRESS_RE = re.compile(r"^iaiso://(?P<identity>[^@/]+)@(?P<locator>[^/]+)(?P<rest>/.*)?$")


class FingerprintError(ValueError):
    """Raised when a fingerprint is malformed or fails schema validation."""


@dataclass
class Address:
    identity: str
    locator: str
    capability: str | None
    raw: str


def parse_address(addr: str) -> Address:
    """Parse an ``iaiso://<identity>@<placement-locator>/<capability>`` address.

    The placement-locator encodes stack layer + region + jurisdiction +
    topology so a router can decide residency and fleet-weight from the address
    alone, before fetching the full fingerprint.
    """
    m = _ADDRESS_RE.match(addr)
    if not m:
        raise FingerprintError(f"not an iaiso:// address: {addr!r}")
    rest = (m.group("rest") or "").strip("/")
    capability = rest.split("/")[-1] if rest else None
    return Address(
        identity=m.group("identity"),
        locator=m.group("locator"),
        capability=capability,
        raw=addr,
    )


def _schema_text() -> str:
    """Load the packaged fingerprint schema (works installed or from source)."""
    try:
        return (resources.files("smartfabric") / "schema" / "fingerprint.schema.json").read_text()
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        # source layout fallback: <repo>/schema/fingerprint.schema.json
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "schema" / "fingerprint.schema.json"
            if candidate.exists():
                return candidate.read_text()
        raise FingerprintError("fingerprint schema not found on disk")


def load_schema() -> dict[str, Any]:
    return json.loads(_schema_text())


def validate(fingerprint: dict[str, Any]) -> list[str]:
    """Validate a fingerprint against the schema. Returns a list of error
    strings (empty == valid). Never raises for validation failures — the caller
    decides whether an invalid fingerprint is fatal."""
    if jsonschema is None:  # pragma: no cover
        raise FingerprintError("jsonschema is not installed")
    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(fingerprint), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]


def load(path: str | Path) -> dict[str, Any]:
    """Load a fingerprint from disk (does not validate)."""
    try:
        return json.loads(Path(path).read_text())
    except json.JSONDecodeError as exc:
        raise FingerprintError(f"invalid JSON in {path}: {exc}") from exc


def posture(fingerprint: dict[str, Any]) -> dict[str, Any]:
    """Return the ``iaiso`` containment posture block (or {} if absent).

    A node with no posture block is treated as *ungoverned*: discoverable, but
    the fabric grants it zero expansion trust and routes no governed flow to it.
    """
    return fingerprint.get("iaiso", {}) or {}


def is_governed(fingerprint: dict[str, Any]) -> bool:
    """A node is governed iff it publishes a posture block with a pressure config."""
    p = posture(fingerprint)
    return bool(p) and "pressure" in p
