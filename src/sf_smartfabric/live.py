"""Live conformance — FAB-L-* checks that drive a *running* node over the wire.

Static FAB-* checks verify what a node declares; behavioural vectors verify what
an implementation computes; these verify what a running node *does* over HTTP.
This is the milestone the transport layer unlocks: proving enforcement
(consent-gating, escalation, atomic release, global halt) actually fires on the
wire, not just in a unit test.

A conformant node must pass every FAB-L check. `--spawn` runs an in-process node
so CI needs no orchestration.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from .models import CIRHeader, CIRMessage
from .wire import decode, encode


@dataclass
class LiveResult:
    id: str
    title: str
    ok: bool
    detail: str = ""


def _post(url: str, msg: CIRMessage) -> dict:
    req = urllib.request.Request(url + "/cir", data=encode(msg),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read()
    reply = decode(body)
    return reply.body.get("payload", {})


def _msg(verb: str, *, token: str | None = None, payload: dict | None = None,
         n: int = 0) -> CIRMessage:
    auth = {"token": token} if token else {}
    return CIRMessage(
        header=CIRHeader(id=f"01LIVE{n:020d}", verb=verb, verb_version="0.1",
                         from_addr="iaiso://harness@local/test",
                         to_addr="iaiso://node@local/demo"),
        body={"schema_ref": f"{verb}/1", "payload": payload or {}},
        auth=auth,
    )


def run(url: str) -> list[LiveResult]:
    results: list[LiveResult] = []

    # FAB-L-001: describe returns a fingerprint
    try:
        p = _post(url, _msg("describe", n=1))
        ok = "fingerprint" in p and "iaiso" in p["fingerprint"]
        results.append(LiveResult("FAB-L-001", "describe returns a governed fingerprint", ok,
                                  "" if ok else "no fingerprint/iaiso posture in reply"))
    except Exception as exc:
        results.append(LiveResult("FAB-L-001", "describe returns a governed fingerprint", False, str(exc)))

    # FAB-L-002: expanding verb WITHOUT consent is denied (invariant 4, default deny)
    try:
        p = _post(url, _msg("invoke", payload={"tokens": 1000}, n=2))
        err = p.get("error", {})
        ok = err.get("code") == "policy" and "consent" in err.get("message", "").lower()
        results.append(LiveResult("FAB-L-002", "expanding verb without ConsentScope is denied (inv. 4)",
                                  ok, "" if ok else f"expected policy/consent denial, got {p}"))
    except Exception as exc:
        results.append(LiveResult("FAB-L-002", "expanding verb without ConsentScope is denied (inv. 4)", False, str(exc)))

    # FAB-L-003: expanding verb WITH consent is accepted and advances pressure
    try:
        p = _post(url, _msg("invoke", token="consent-demo-jwt", payload={"tokens": 20000, "tool_calls": 2}, n=3))
        ok = p.get("accepted") is True and p.get("p", 0) > 0
        results.append(LiveResult("FAB-L-003", "expanding verb with ConsentScope advances pressure",
                                  ok, "" if ok else f"not accepted / no pressure: {p}"))
    except Exception as exc:
        results.append(LiveResult("FAB-L-003", "expanding verb with ConsentScope advances pressure", False, str(exc)))

    # FAB-L-004: pressure.sample reports a valid zone
    try:
        p = _post(url, _msg("pressure.sample", n=4))
        ok = p.get("zone") in ("nominal", "warning", "escalation", "release") and "p" in p
        results.append(LiveResult("FAB-L-004", "pressure.sample reports {p, dpdt, zone}", ok,
                                  "" if ok else f"bad sample: {p}"))
    except Exception as exc:
        results.append(LiveResult("FAB-L-004", "pressure.sample reports {p, dpdt, zone}", False, str(exc)))

    # FAB-L-005: sustained load drives escalation then atomic release (inv. 2)
    try:
        _post(url, _msg("reset", n=99))  # clean slate for a deterministic climb
        released = False
        escalated = False
        for i in range(30):
            p = _post(url, _msg("invoke", token="consent-demo-jwt",
                                payload={"tokens": 6000, "tool_calls": 0}, n=100 + i))
            if p.get("zone") == "escalation" or p.get("escalation"):
                escalated = True
            if p.get("released"):
                released = True
                break
        # after release, pressure must have reset to 0
        s = _post(url, _msg("pressure.sample", n=200))
        ok = released and escalated and s.get("p") == 0.0
        results.append(LiveResult("FAB-L-005", "load drives escalation then atomic release+reset (inv. 2/4)",
                                  ok, "" if ok else f"escalated={escalated} released={released} post_p={s.get('p')}"))
    except Exception as exc:
        results.append(LiveResult("FAB-L-005", "load drives escalation then atomic release+reset (inv. 2/4)", False, str(exc)))

    # FAB-L-006: after halt.global, expanding verbs are rejected (Layer 6)
    try:
        _post(url, _msg("reset", n=300))  # clear any post-release lock first
        _post(url, _msg("halt.global", n=301))
        p = _post(url, _msg("invoke", token="consent-demo-jwt", payload={"tokens": 1000}, n=302))
        err = p.get("error", {})
        ok = err.get("code") == "policy" and "halt" in err.get("message", "").lower()
        results.append(LiveResult("FAB-L-006", "Layer-6 global halt blocks further expansion", ok,
                                  "" if ok else f"expected halt denial, got {p}"))
    except Exception as exc:
        results.append(LiveResult("FAB-L-006", "Layer-6 global halt blocks further expansion", False, str(exc)))

    return results


def run_spawned() -> list[LiveResult]:
    """Spin up an in-process node, run the harness, tear it down."""
    from .node import serve_in_thread
    server, _node, url = serve_in_thread()
    try:
        return run(url)
    finally:
        server.shutdown()


def summarize(results: list[LiveResult]) -> dict[str, int]:
    out = {"pass": 0, "fail": 0}
    for r in results:
        out["pass" if r.ok else "fail"] += 1
    return out
