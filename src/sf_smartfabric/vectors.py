"""Behavioral conformance vectors — the runnable contract.

Static ``FAB-*`` checks (conformance.py) verify what a node *declares*. These
vectors verify what an implementation *computes*: given a pinned input, does it
produce the pinned output? Any implementation, in any language, is IFP-behavioral-
conformant iff it passes every vector here. This is the QUIC-interop / WPT model,
and it is what makes a *second* implementation meaningful — both must pass the
same vectors, byte-for-byte where the vector is byte-typed and within 1e-9 where
it is numeric.

Three vector families ship in ``spec/vectors/``:
  * ``pressure.vectors.json`` — input step sequences -> pressure trajectory,
    zones, release/lock. Numeric tolerance 1e-9 (the core's own tolerance).
  * ``fleet.vectors.json``    — node samples -> P_fleet, peak, hot nodes.
  * ``envelope.vectors.json`` — CIR messages -> canonical-JSON bytes, sha256, and
    framed hex. Byte-exact: cross-language serializers must agree exactly.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .conformance import run as run_conformance
from .fingerprint import validate as validate_fp
from .pressure import NodeSample, PressureConfig, PressureEngine, fleet_pressure
from .wire import encode, frame_message, decode

TOLERANCE = 1e-9


@dataclass
class VectorResult:
    family: str
    name: str
    ok: bool
    detail: str = ""


def _load(name: str) -> Any:
    """Load a bundled vector file from spec/vectors/ (source or installed)."""
    parts = ("spec", "vectors", name)
    try:
        ref = resources.files("sf-smartfabric")
        for p in parts:
            ref = ref / p
        return json.loads(ref.read_text())
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        here = Path(__file__).resolve()
        for parent in here.parents:
            cand = parent.joinpath(*parts)
            if cand.exists():
                return json.loads(cand.read_text())
        raise FileNotFoundError("/".join(parts))


def _approx(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE


# --------------------------------------------------------------------------- #
# Pressure                                                                    #
# --------------------------------------------------------------------------- #

def _run_pressure(case: dict[str, Any]) -> VectorResult:
    cfg = PressureConfig(**case.get("config", {}))
    eng = PressureEngine(cfg)
    got = []
    for step in case["steps"]:
        out = eng.step(
            tokens=step.get("tokens", 0),
            tool_calls=step.get("tool_calls", 0),
            depth=step.get("depth", 0),
            seconds=step.get("seconds", 0.0),
        )
        got.append({"p": out.pressure, "zone": out.zone.value,
                    "released": out.released, "locked": out.locked})
    exp = case["expect"]
    if len(got) != len(exp):
        return VectorResult("pressure", case["name"], False,
                            f"step count {len(got)} != {len(exp)}")
    for i, (g, e) in enumerate(zip(got, exp)):
        if not _approx(g["p"], e["p"]):
            return VectorResult("pressure", case["name"], False,
                                f"step {i}: p {g['p']:.12f} != {e['p']:.12f}")
        for k in ("zone", "released", "locked"):
            if g[k] != e[k]:
                return VectorResult("pressure", case["name"], False,
                                    f"step {i}: {k} {g[k]!r} != {e[k]!r}")
    return VectorResult("pressure", case["name"], True)


# --------------------------------------------------------------------------- #
# Fleet                                                                       #
# --------------------------------------------------------------------------- #

def _run_fleet(case: dict[str, Any]) -> VectorResult:
    samples = [NodeSample(**n) for n in case["nodes"]]
    res = fleet_pressure(samples, escalation_threshold=case.get("escalation_threshold", 0.85))
    exp = case["expect"]
    if not _approx(res.value, exp["P_fleet"]):
        return VectorResult("fleet", case["name"], False,
                            f"P_fleet {res.value:.12f} != {exp['P_fleet']:.12f}")
    if res.peak_node != exp["peak_node"]:
        return VectorResult("fleet", case["name"], False,
                            f"peak {res.peak_node!r} != {exp['peak_node']!r}")
    if sorted(res.hot_nodes) != sorted(exp["hot_nodes"]):
        return VectorResult("fleet", case["name"], False,
                            f"hot {res.hot_nodes} != {exp['hot_nodes']}")
    return VectorResult("fleet", case["name"], True)


# --------------------------------------------------------------------------- #
# Envelope (byte-exact cross-language interop)                                #
# --------------------------------------------------------------------------- #

def _build_message(spec: dict[str, Any]):
    """Reconstruct a CIRMessage from a vector's structural 'message' block."""
    return decode(spec)  # the vector stores the message in canonical dict form


def _run_envelope(case: dict[str, Any]) -> VectorResult:
    msg = _build_message(case["message"])
    canon = encode(msg)
    exp = case["expect"]
    if canon.decode("utf-8") != exp["canonical_json"]:
        return VectorResult("envelope", case["name"], False,
                            "canonical_json mismatch")
    sha = "sha256:" + hashlib.sha256(canon).hexdigest()
    if sha != exp["canonical_sha256"]:
        return VectorResult("envelope", case["name"], False,
                            f"sha {sha} != {exp['canonical_sha256']}")
    framed = frame_message(msg).hex()
    if framed != exp["framed_hex"]:
        return VectorResult("envelope", case["name"], False, "framed_hex mismatch")
    # round-trip: decode(encode(x)) canonicalizes identically
    if encode(decode(canon)) != canon:
        return VectorResult("envelope", case["name"], False, "round-trip not stable")
    return VectorResult("envelope", case["name"], True)


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #

_RUNNERS = {
    "pressure": ("pressure.vectors.json", _run_pressure),
    "fleet": ("fleet.vectors.json", _run_fleet),
    "envelope": ("envelope.vectors.json", _run_envelope),
}


def run_all() -> list[VectorResult]:
    results: list[VectorResult] = []
    for family, (fname, runner) in _RUNNERS.items():
        data = _load(fname)
        for case in data["cases"]:
            try:
                results.append(runner(case))
            except Exception as exc:  # a broken case must not abort the run
                results.append(VectorResult(family, case.get("name", "?"), False,
                                            f"error: {exc}"))
    return results


def summarize(results: list[VectorResult]) -> dict[str, int]:
    out = {"pass": 0, "fail": 0}
    for r in results:
        out["pass" if r.ok else "fail"] += 1
    return out
