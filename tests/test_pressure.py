"""Pressure model tests — determinism, thresholds, release/lock, fleet."""
import pytest

from sf_smartfabric import (
    NodeSample,
    PressureConfig,
    PressureEngine,
    Zone,
    fleet_pressure,
)


def test_defaults_match_core():
    c = PressureConfig()
    assert c.escalation_threshold == 0.85
    assert c.release_threshold == 0.95
    assert c.token_coefficient == 0.015
    assert c.tool_coefficient == 0.08
    assert c.depth_coefficient == 0.05
    assert c.post_release_lock is True


def test_config_validation_rejects_bad_thresholds():
    with pytest.raises(ValueError):
        PressureEngine(PressureConfig(escalation_threshold=0.9, release_threshold=0.8))
    with pytest.raises(ValueError):
        PressureEngine(PressureConfig(token_coefficient=-1))
    with pytest.raises(ValueError):
        PressureEngine(PressureConfig(escalation_threshold=1.5))


def test_intake_accumulates_deterministically():
    a = PressureEngine()
    b = PressureEngine()
    for _ in range(5):
        oa = a.step(tokens=1000, tool_calls=1)
        ob = b.step(tokens=1000, tool_calls=1)
        assert oa.pressure == pytest.approx(ob.pressure, abs=1e-9)


def test_single_step_math():
    # 2000 tokens * 0.015/1k + 1 tool * 0.08 + depth 2 * 0.05 - 0.02 dissipation
    eng = PressureEngine()
    out = eng.step(tokens=2000, tool_calls=1, depth=2)
    expected = (2000 / 1000) * 0.015 + 1 * 0.08 + 2 * 0.05 - 0.02
    assert out.pressure == pytest.approx(expected, abs=1e-9)


def test_zones():
    eng = PressureEngine()
    assert eng.zone(0.10) is Zone.NOMINAL
    assert eng.zone(0.72) is Zone.WARNING
    assert eng.zone(0.88) is Zone.ESCALATION
    assert eng.zone(0.96) is Zone.RELEASE


def test_release_wipes_and_locks():
    eng = PressureEngine()
    released = False
    for _ in range(50):
        out = eng.step(tokens=5000, tool_calls=3)
        if out.released:
            released = True
            assert out.pressure == 0.0
            assert out.zone is Zone.RELEASE
            assert eng.locked is True
            break
    assert released, "workload should have reached release"

    # locked: further input refused until reset
    out2 = eng.step(tokens=5000, tool_calls=3)
    assert out2.locked is True
    assert out2.pressure == 0.0

    eng.reset()
    assert eng.locked is False
    out3 = eng.step(tokens=4000, tool_calls=1)  # intake must exceed per-step dissipation
    assert out3.pressure > 0.0


def test_pressure_never_exceeds_one():
    # invariant 1: bounded pressure
    eng = PressureEngine(PressureConfig(post_release_lock=False))
    for _ in range(200):
        out = eng.step(tokens=100000, tool_calls=50)
        assert 0.0 <= out.pressure <= 1.0


def test_fleet_pressure_weights_hubs():
    samples = [
        NodeSample("hub", pressure=0.9, centrality=0.9),
        NodeSample("leaf", pressure=0.1, centrality=0.1),
    ]
    weighted = fleet_pressure(samples).value
    naive = (0.9 + 0.1) / 2
    # hub dominates -> weighted mean above the naive mean
    assert weighted > naive
    assert weighted == pytest.approx((0.9 * 0.9 + 0.1 * 0.1) / (0.9 + 0.1), abs=1e-9)


def test_fleet_pressure_reports_hot_nodes():
    samples = [
        NodeSample("a", 0.88, 1.0),
        NodeSample("b", 0.40, 1.0),
        NodeSample("c", 0.86, 1.0),
    ]
    result = fleet_pressure(samples, escalation_threshold=0.85)
    assert result.hot_nodes == ["a", "c"]
    assert result.peak_node == "a"


def test_fleet_pressure_empty():
    result = fleet_pressure([])
    assert result.value == 0.0
    assert result.peak_node is None
