"""Conformance: run the FAB-* checks against a node fingerprint and emit a
report a node can carry in its own fingerprint.

The Smart* family uses namespaced ``PREFIX-*`` rule IDs (SmartPangolin's
``SEC-*``, SmartSeal's ``SEAL-*``); the fabric's analog is the **conformance
check ID** ``FAB-*``. Each check is one MUST/SHOULD from docs/06, made
executable against the machine-readable fingerprint.

These are *static* checks: they verify what a node *declares* and whether the
declaration is internally consistent and complete. They do not (and cannot,
from a fingerprint alone) prove runtime behaviour — a live conformance harness
that drives a node's endpoints is future work (see private/roadmap). The report
says exactly which class of check ran.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from . import fingerprint as fp
from .models import CIR_VERBS, is_known_verb


class Level(str, Enum):
    MUST = "MUST"
    SHOULD = "SHOULD"


class Result(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"  # not applicable to this node


@dataclass
class CheckResult:
    id: str
    title: str
    level: Level
    result: Result
    detail: str = ""


@dataclass
class Report:
    node: str
    suite_version: str
    ran_at: str
    checks: list[CheckResult] = field(default_factory=list)
    signature: str | None = None

    @property
    def must_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.level is Level.MUST and c.result is Result.FAIL]

    @property
    def passed(self) -> bool:
        return not self.must_failures

    def summary(self) -> dict[str, int]:
        out = {"pass": 0, "fail": 0, "skip": 0}
        for c in self.checks:
            out[c.result.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "suite_version": self.suite_version,
            "ran_at": self.ran_at,
            "results": {
                "must": "pass" if self.passed else "fail",
                "counts": self.summary(),
            },
            "checks": [
                {
                    "id": c.id,
                    "title": c.title,
                    "level": c.level.value,
                    "result": c.result.value,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
            "signature": self.signature,
        }


SUITE_VERSION = "0.1.0"

# A check is a function fingerprint -> (Result, detail).
Check = Callable[[dict[str, Any]], "tuple[Result, str]"]
_REGISTRY: list[tuple[str, str, Level, Check]] = []


def _check(cid: str, title: str, level: Level):
    def deco(fn: Check) -> Check:
        _REGISTRY.append((cid, title, level, fn))
        return fn
    return deco


def _ok() -> "tuple[Result, str]":
    return Result.PASS, ""


# --------------------------------------------------------------------------- #
# Structural MUST checks (docs/06 · Core)                                      #
# --------------------------------------------------------------------------- #

@_check("FAB-C-001", "Publishes a schema-valid fingerprint", Level.MUST)
def _c001(f: dict[str, Any]):
    errs = fp.validate(f)
    return (_ok() if not errs else (Result.FAIL, "; ".join(errs[:5])))


@_check("FAB-C-002", "Declares every port with full port hygiene", Level.MUST)
def _c002(f: dict[str, Any]):
    ports = f.get("ports", [])
    if not ports:
        return Result.FAIL, "no ports declared"
    required = {"number", "transport", "binding", "tls", "plane", "direction"}
    for i, p in enumerate(ports):
        missing = required - set(p)
        if missing:
            return Result.FAIL, f"port[{i}] missing {sorted(missing)}"
    return _ok()


@_check("FAB-C-003", "Implements only known CIR verbs at declared versions", Level.MUST)
def _c003(f: dict[str, Any]):
    verbs = f.get("cir", {}).get("verbs", [])
    if not verbs:
        return Result.FAIL, "no CIR verbs declared"
    unknown = [v.get("verb") for v in verbs if not is_known_verb(v.get("verb", ""))]
    if unknown:
        return Result.FAIL, f"unknown verbs (not in closed set): {unknown}"
    if not any(v.get("verb") == "describe" for v in verbs):
        return Result.FAIL, "missing mandatory 'describe' verb"
    return _ok()


@_check("FAB-C-004", "CIR command-translation mapping targets known verbs", Level.MUST)
def _c004(f: dict[str, Any]):
    mapping = f.get("cir", {}).get("mapping", [])
    for i, row in enumerate(mapping):
        if not is_known_verb(row.get("cir_verb", "")):
            return Result.FAIL, f"mapping[{i}] -> unknown cir_verb {row.get('cir_verb')!r}"
    return _ok()


@_check("FAB-C-005", "mTLS + TLS 1.3 declared for governed transport", Level.MUST)
def _c005(f: dict[str, Any]):
    std = f.get("standards", {})
    ident = set(std.get("identity", []))
    crypto = set(std.get("crypto", []))
    if "mtls" not in ident:
        return Result.FAIL, "mtls not declared in standards.identity"
    if "tls1.3" not in crypto:
        return Result.FAIL, "tls1.3 not declared in standards.crypto"
    return _ok()


@_check("FAB-C-006", "Emits provenance + OpenTelemetry (observability plane)", Level.MUST)
def _c006(f: dict[str, Any]):
    std = f.get("standards", {})
    obs = set(std.get("observability", []))
    gov = set(std.get("governance", []))
    if not obs & {"otel-traces", "otel-metrics", "otel-logs"}:
        return Result.FAIL, "no OpenTelemetry signal declared"
    if not any(g.startswith("provenance/") for g in gov):
        return Result.FAIL, "no provenance/* governance standard declared"
    return _ok()


@_check("FAB-C-007", "Resolvable iaiso:// address with placement locator", Level.MUST)
def _c007(f: dict[str, Any]):
    addr = f.get("identity", {}).get("address")
    if not addr:
        return Result.FAIL, "identity.address absent"
    try:
        fp.parse_address(addr)
    except fp.FingerprintError as exc:
        return Result.FAIL, str(exc)
    return _ok()


# --------------------------------------------------------------------------- #
# IAIso containment MUST checks (docs/06 · binds to the core, docs/07)         #
# --------------------------------------------------------------------------- #

@_check("FAB-I-001", "Publishes an iaiso containment posture block", Level.MUST)
def _i001(f: dict[str, Any]):
    if not fp.is_governed(f):
        return Result.FAIL, "no iaiso posture block (node is ungoverned)"
    return _ok()


@_check("FAB-I-002", "Pressure config present and core-consistent", Level.MUST)
def _i002(f: dict[str, Any]):
    p = fp.posture(f).get("pressure", {})
    if not p:
        return Result.SKIP, "no posture block"
    et, rt = p.get("escalation_threshold"), p.get("release_threshold")
    if et is None or rt is None:
        return Result.FAIL, "escalation_threshold/release_threshold required"
    if not (0 <= et <= 1 and 0 <= rt <= 1):
        return Result.FAIL, "thresholds outside [0,1]"
    if rt <= et:
        return Result.FAIL, "release_threshold must exceed escalation_threshold"
    return _ok()


@_check("FAB-I-003", "Declares a clocked-evaluation interval (invariant 3)", Level.MUST)
def _i003(f: dict[str, Any]):
    p = fp.posture(f).get("pressure", {})
    if not p:
        return Result.SKIP, "no posture block"
    if not p.get("clock_ms"):
        return Result.FAIL, "pressure.clock_ms required (no continuous ungoverned loops)"
    return _ok()


@_check("FAB-I-004", "Consent issuer declared when scope required (invariant 4)", Level.MUST)
def _i004(f: dict[str, Any]):
    post = fp.posture(f)
    if not post:
        return Result.SKIP, "no posture block"
    consent = post.get("consent", {})
    if consent.get("scope_required") and not consent.get("issuer"):
        return Result.FAIL, "scope_required but no consent.issuer"
    return _ok()


@_check("FAB-I-005", "Reset declared lossy (invariant 2)", Level.MUST)
def _i005(f: dict[str, Any]):
    post = fp.posture(f)
    if not post:
        return Result.SKIP, "no posture block"
    reset = post.get("reset", {})
    if reset and reset.get("lossy") is False:
        return Result.FAIL, "reset.lossy=false violates 'no learning across resets'"
    return _ok()


@_check("FAB-I-006", "Layer-0 caps hardware-attested if Layer 0 enforced", Level.MUST)
def _i006(f: dict[str, Any]):
    post = fp.posture(f)
    if not post:
        return Result.SKIP, "no posture block"
    if 0 in (post.get("enforced_layers") or []):
        caps = post.get("layer0_caps", {})
        if not caps.get("hardware_attested"):
            return Result.FAIL, "enforces Layer 0 but layer0_caps.hardware_attested is not true"
    return _ok()


# --------------------------------------------------------------------------- #
# Placement / governance SHOULD checks (docs/06)                              #
# --------------------------------------------------------------------------- #

@_check("FAB-G-001", "Jurisdiction + egress posture declared", Level.SHOULD)
def _g001(f: dict[str, Any]):
    j = f.get("placement", {}).get("l8_jurisdiction", {})
    if not j.get("country") or not j.get("egress"):
        return Result.FAIL, "l8_jurisdiction.country/egress recommended"
    return _ok()


@_check("FAB-G-002", "adaptive/autonomous nodes expose override obligations", Level.SHOULD)
def _g002(f: dict[str, Any]):
    dyn = f.get("placement", {}).get("l10_dynamics", {})
    cls = dyn.get("influence_class")
    if cls in ("adaptive", "autonomous"):
        layers = fp.posture(f).get("enforced_layers", [])
        need = 4 if cls == "adaptive" else 6
        if need not in layers:
            return Result.FAIL, f"{cls} node should enforce Layer {need} (override/kill-switch)"
    return _ok()


@_check("FAB-G-003", "Resource-accounting / cost standard declared", Level.SHOULD)
def _g003(f: dict[str, Any]):
    gov = set(f.get("standards", {}).get("governance", []))
    dom = set(f.get("standards", {}).get("domain", []))
    if not (any(g.startswith("iaiso-policy") for g in gov) or "smartllmcost" in dom):
        return Result.FAIL, "declare iaiso-policy/* or reuse smartllmcost for accounting"
    return _ok()


def run(fingerprint: dict[str, Any], *, sign: bool = True) -> Report:
    """Run every registered FAB-* check and assemble a report."""
    node = fingerprint.get("identity", {}).get("address") or fingerprint.get(
        "identity", {}
    ).get("id", "<unknown>")
    checks: list[CheckResult] = []
    for cid, title, level, fn in _REGISTRY:
        try:
            result, detail = fn(fingerprint)
        except Exception as exc:  # a broken check must not crash the run
            result, detail = Result.FAIL, f"check error: {exc}"
        checks.append(CheckResult(cid, title, level, result, detail))

    report = Report(
        node=node,
        suite_version=SUITE_VERSION,
        ran_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        checks=checks,
    )
    if sign:
        # A content digest stands in for a real ed25519 signature until a key is
        # wired in (see private/roadmap). It is deterministic over the results.
        payload = json.dumps(
            [[c.id, c.result.value] for c in checks], separators=(",", ":")
        ).encode()
        report.signature = "sha256:" + hashlib.sha256(payload).hexdigest()
    return report


def check_ids() -> list[str]:
    return [cid for cid, *_ in _REGISTRY]
