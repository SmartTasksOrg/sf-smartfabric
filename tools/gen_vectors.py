"""Generate the behavioral vector files from the Python reference implementation.

The Python engine is the source of truth; this script freezes its outputs into
spec/vectors/*.json. A second implementation (ports/node) must then reproduce
these exactly. Re-run only when the *intended* behaviour changes — a vector diff
in CI otherwise means a regression.

Usage:  python tools/gen_vectors.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sf_smartfabric.pressure import NodeSample, PressureConfig, PressureEngine, fleet_pressure
from sf_smartfabric.wire import encode, frame_message, decode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "spec" / "vectors"


def gen_pressure():
    cases = []

    def trace(name, config, steps):
        eng = PressureEngine(PressureConfig(**config))
        expect = []
        for s in steps:
            out = eng.step(**s)
            expect.append({"p": round(out.pressure, 12), "zone": out.zone.value,
                           "released": out.released, "locked": out.locked})
        cases.append({"name": name, "config": config, "steps": steps, "expect": expect})

    # 1. defaults, climb to release then locked
    trace("defaults-climb-to-release", {},
          [{"tokens": 1200, "tool_calls": 2, "depth": 1} for _ in range(6)])
    # 2. dissipation-dominated: pressure decays / floors at 0
    trace("dissipation-floor", {"token_coefficient": 0.0, "tool_coefficient": 0.0,
                                "depth_coefficient": 0.0, "dissipation_per_step": 0.05},
          [{"tokens": 0} for _ in range(4)])
    # 3. warning band boundary
    trace("warning-band", {"dissipation_per_step": 0.0},
          [{"tokens": 46667}])  # 46.667k * 0.015 = 0.700005 -> warning
    # 4. no post-release lock: keeps cycling
    trace("no-lock-cycles", {"post_release_lock": False},
          [{"tokens": 40000, "tool_calls": 5} for _ in range(4)])
    # 5. depth-driven planning pressure
    trace("depth-driven", {"token_coefficient": 0.0, "tool_coefficient": 0.0},
          [{"depth": 10}, {"depth": 10}])
    # 6. seconds-based dissipation
    trace("timed-dissipation", {"dissipation_per_step": 0.0, "dissipation_per_second": 0.1},
          [{"tokens": 20000, "seconds": 1.0}, {"tokens": 0, "seconds": 2.0}])

    (OUT / "pressure.vectors.json").write_text(
        json.dumps({"family": "pressure", "tolerance": 1e-9, "cases": cases}, indent=2) + "\n")
    print(f"pressure: {len(cases)} cases")


def gen_fleet():
    cases = []

    def case(name, et, nodes):
        samples = [NodeSample(**n) for n in nodes]
        res = fleet_pressure(samples, escalation_threshold=et)
        cases.append({"name": name, "escalation_threshold": et, "nodes": nodes,
                      "expect": {"P_fleet": round(res.value, 12),
                                 "peak_node": res.peak_node,
                                 "hot_nodes": res.hot_nodes}})

    case("scale-free-hub", 0.85, [
        {"node_id": "hub", "pressure": 0.88, "centrality": 0.92},
        {"node_id": "mid", "pressure": 0.71, "centrality": 0.82},
        {"node_id": "leaf", "pressure": 0.12, "centrality": 0.08},
    ])
    case("uniform", 0.85, [
        {"node_id": "a", "pressure": 0.5, "centrality": 1.0},
        {"node_id": "b", "pressure": 0.5, "centrality": 1.0},
    ])
    case("all-hot", 0.80, [
        {"node_id": "x", "pressure": 0.90, "centrality": 1.0},
        {"node_id": "y", "pressure": 0.85, "centrality": 1.0},
    ])
    case("zero-centrality", 0.85, [
        {"node_id": "a", "pressure": 0.6, "centrality": 0.0},
        {"node_id": "b", "pressure": 0.4, "centrality": 0.0},
    ])
    case("empty", 0.85, [])

    (OUT / "fleet.vectors.json").write_text(
        json.dumps({"family": "fleet", "tolerance": 1e-9, "cases": cases}, indent=2) + "\n")
    print(f"fleet: {len(cases)} cases")


def gen_envelope():
    cases = []

    def case(name, message):
        msg = decode(message)
        canon = encode(msg)
        expect = {
            "canonical_json": canon.decode("utf-8"),
            "canonical_sha256": "sha256:" + hashlib.sha256(canon).hexdigest(),
            "framed_hex": frame_message(msg).hex(),
        }
        # store the message back in its own canonical dict form for stability
        cases.append({"name": name, "message": json.loads(canon), "expect": expect})

    case("minimal-invoke", {
        "header": {"id": "01J9Z8INVOKE00000000000001", "verb": "invoke",
                   "verb_version": "0.1",
                   "from": "iaiso://a@dc1/text.generate",
                   "to": "iaiso://b@dc1/text.generate"},
        "policy": {"audit_required": True},
    })
    case("full-with-consent", {
        "header": {"id": "01J9Z8FULL0000000000000002", "verb": "invoke",
                   "verb_version": "0.1",
                   "from": "iaiso://client@us.east/agent",
                   "to": "iaiso://model-7@cn.bj/text.generate",
                   "idempotency": "idem-abc-123",
                   "trace": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
                   "deadline_ms": 30000, "qos_profile": "interactive-low-latency"},
        "auth": {"token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudCJ9.sig", "sig": "ed25519:deadbeef"},
        "body": {"schema_ref": "text.generate/1", "payload": {"messages": [{"role": "user", "content": "hi"}]}},
        "policy": {"residency": "CN", "influence_class": "informational", "audit_required": True},
        "meta": {"placement_hint": "cn.bj.az2", "cost_hint": "smartllmcost"},
    })
    case("pressure-sample", {
        "header": {"id": "01J9Z8PSAMPLE0000000000003", "verb": "pressure.sample",
                   "verb_version": "0.1",
                   "from": "iaiso://model-7@cn.bj/text.generate",
                   "to": "iaiso://aggregator@fabric/pressure"},
        "body": {"schema_ref": "pressure.sample/1",
                 "payload": {"p": 0.83, "dpdt": 0.05, "zone": "warning", "clock_seq": 42}},
        "policy": {"audit_required": True},
    })
    case("halt-global", {
        "header": {"id": "01J9Z8HALT00000000000000004", "verb": "halt.global",
                   "verb_version": "0.1",
                   "from": "iaiso://halt-controller@fabric/existential",
                   "to": "iaiso://all@fabric"},
        "body": {"schema_ref": "halt.global/1",
                 "payload": {"origin": "halt-controller", "reason": "L6 trip", "drain": False}},
        "policy": {"audit_required": True},
    })

    (OUT / "envelope.vectors.json").write_text(
        json.dumps({"family": "envelope", "encoding": "canonical-json", "cases": cases}, indent=2) + "\n")
    print(f"envelope: {len(cases)} cases")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    gen_pressure()
    gen_fleet()
    gen_envelope()
    print(f"wrote vectors to {OUT}")
