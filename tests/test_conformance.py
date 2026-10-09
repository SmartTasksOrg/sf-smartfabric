"""Conformance tests — the example passes; specific breakages fail the right check."""
import copy
import json
from pathlib import Path

import pytest

from sf_smartfabric import conformance
from sf_smartfabric.conformance import Level, Result

EXAMPLE = Path(__file__).resolve().parents[1] / "schema" / "example.fingerprint.json"


@pytest.fixture
def example():
    return json.loads(EXAMPLE.read_text())


def _by_id(report, cid):
    return next(c for c in report.checks if c.id == cid)


def test_example_passes_all_musts(example):
    report = conformance.run(example)
    assert report.passed, [c.id for c in report.must_failures]


def test_report_is_signed_and_serializable(example):
    report = conformance.run(example)
    assert report.signature and report.signature.startswith("sha256:")
    d = report.to_dict()
    # round-trips as JSON
    assert json.loads(json.dumps(d))["results"]["must"] == "pass"


def test_ungoverned_node_fails_posture(example):
    ungoverned = copy.deepcopy(example)
    ungoverned.pop("iaiso")
    report = conformance.run(ungoverned)
    assert not report.passed
    assert _by_id(report, "FAB-I-001").result is Result.FAIL


def test_missing_mtls_fails_security(example):
    broken = copy.deepcopy(example)
    broken["standards"]["identity"] = ["oidc"]
    report = conformance.run(broken)
    assert _by_id(report, "FAB-C-005").result is Result.FAIL


def test_unknown_verb_fails(example):
    broken = copy.deepcopy(example)
    broken["cir"]["verbs"].append({"verb": "teleport", "version": "0.1"})
    report = conformance.run(broken)
    assert _by_id(report, "FAB-C-003").result is Result.FAIL


def test_extension_verb_allowed(example):
    ok = copy.deepcopy(example)
    ok["cir"]["verbs"].append({"verb": "x-acme-warp", "version": "0.1"})
    report = conformance.run(ok)
    assert _by_id(report, "FAB-C-003").result is Result.PASS


def test_layer0_without_attestation_fails(example):
    broken = copy.deepcopy(example)
    broken["iaiso"]["layer0_caps"]["hardware_attested"] = False
    report = conformance.run(broken)
    assert _by_id(report, "FAB-I-006").result is Result.FAIL


def test_lossy_false_reset_fails(example):
    broken = copy.deepcopy(example)
    broken["iaiso"]["reset"]["lossy"] = False
    report = conformance.run(broken)
    assert _by_id(report, "FAB-I-005").result is Result.FAIL


def test_autonomous_needs_layer6(example):
    broken = copy.deepcopy(example)
    broken["placement"]["l10_dynamics"]["influence_class"] = "autonomous"
    # example does not enforce layer 6
    report = conformance.run(broken)
    assert _by_id(report, "FAB-G-002").result is Result.FAIL
    assert _by_id(report, "FAB-G-002").level is Level.SHOULD  # doesn't block MUST-pass


def test_check_ids_are_unique():
    ids = conformance.check_ids()
    assert len(ids) == len(set(ids))
