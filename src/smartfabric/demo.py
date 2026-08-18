"""`smartfabric --demo` — a deterministic, offline tour of the protocol.

Runs three things against bundled synthetic data, no network required:
  1. the single-node pressure model driving a token/tool workload to release,
  2. topology-weighted fleet pressure over the example fleet,
  3. the FAB-* conformance suite over the example fingerprint.
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from . import conformance
from .fingerprint import parse_address
from .pressure import NodeSample, PressureConfig, PressureEngine, fleet_pressure


def _bundled(*parts: str) -> dict:
    """Load a bundled JSON file, whether installed or run from source."""
    try:
        ref = resources.files("smartfabric")
        for p in parts:
            ref = ref / p
        return json.loads(ref.read_text())
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent.joinpath(*parts)
            if candidate.exists():
                return json.loads(candidate.read_text())
        raise FileNotFoundError("/".join(parts))


def _rule(title: str) -> str:
    return f"\n\033[1m{title}\033[0m\n" + "─" * 64


def run() -> int:
    print("SmartFabric — IAIso Fabric Protocol (IFP) · offline demo")
    print("binds to IAIso v5.0 core · pressure · layers 0–6 · 5 invariants")

    # 1. Single-node pressure -------------------------------------------------
    print(_rule("1 · single-node pressure (dp/dt to atomic release)"))
    eng = PressureEngine(PressureConfig())
    print(f"  config: escalation={eng.config.escalation_threshold} "
          f"release={eng.config.release_threshold} "
          f"token_coeff={eng.config.token_coefficient}/1k tool_coeff={eng.config.tool_coefficient}")
    for i in range(1, 9):
        out = eng.step(tokens=1200, tool_calls=2, depth=1)
        flag = " ← ATOMIC RESET (lossy)" if out.released else ""
        print(f"  step {i}: p={out.pressure:0.3f}  zone={out.zone.value:<10}{flag}")
        if out.released:
            break
    print("  (after release the node is locked until reset — invariant 2: no learning across resets)")

    # 2. Fleet pressure -------------------------------------------------------
    print(_rule("2 · fleet pressure (Layer-3 ecosystem coupling, S10-weighted)"))
    fleet = _bundled("examples", "fleet.example.json")
    samples = [NodeSample(**n) for n in fleet["nodes"]]
    fp_result = fleet_pressure(samples, escalation_threshold=fleet["escalation_threshold"])
    for s in samples:
        bar = "█" * int(s.pressure * 24)
        print(f"  {s.node_id:<15} p={s.pressure:0.2f} centrality={s.centrality:0.2f} {bar}")
    print(f"  → P_fleet (centrality-weighted) = {fp_result.value:0.3f}")
    print(f"  → peak node: {fp_result.peak_node} @ {fp_result.peak_pressure:0.2f}")
    print(f"  → hot nodes (≥ escalation): {fp_result.hot_nodes or '—'}")

    # 3. Conformance ----------------------------------------------------------
    print(_rule("3 · FAB-* conformance over the example fingerprint"))
    finger = _bundled("schema", "example.fingerprint.json")
    addr = parse_address(finger["identity"]["address"])
    print(f"  node identity: {addr.identity} @ {addr.locator} · capability={addr.capability}")
    report = conformance.run(finger)
    for c in report.checks:
        mark = {"pass": "\033[32m✓\033[0m", "fail": "\033[31m✗\033[0m", "skip": "·"}[c.result.value]
        detail = f"  — {c.detail}" if c.detail else ""
        print(f"  {mark} {c.id} [{c.level.value}] {c.title}{detail}")
    counts = report.summary()
    verdict = "\033[32mPASS\033[0m" if report.passed else "\033[31mFAIL (MUST failures)\033[0m"
    print(f"\n  verdict: {verdict}  ({counts['pass']} pass / {counts['fail']} fail / {counts['skip']} skip)")
    print(f"  report signature: {report.signature}")

    print("\ndone. See docs/ for the full spec; schema/fingerprint.schema.json is the contract.")
    return 0 if report.passed else 1
