"""Fingerprint tests — schema validity, address parsing, governed detection."""
import copy
import json
from pathlib import Path

import pytest

from sf_smartfabric import fingerprint as fp

EXAMPLE = Path(__file__).resolve().parents[1] / "schema" / "example.fingerprint.json"


@pytest.fixture
def example():
    return json.loads(EXAMPLE.read_text())


def test_example_is_schema_valid(example):
    assert fp.validate(example) == []


def test_missing_required_block_fails(example):
    broken = copy.deepcopy(example)
    del broken["iaiso"]
    errors = fp.validate(broken)
    assert errors and any("iaiso" in e for e in errors)


def test_bad_threshold_fails_schema(example):
    broken = copy.deepcopy(example)
    broken["iaiso"]["pressure"]["escalation_threshold"] = 2.0
    errors = fp.validate(broken)
    assert errors


def test_parse_address():
    a = fp.parse_address(example_addr())
    assert a.identity == "acme-model-7"
    assert a.locator == "cn.bj.az2"
    assert a.capability == "text.generate"


def test_parse_address_rejects_non_iaiso():
    with pytest.raises(fp.FingerprintError):
        fp.parse_address("https://example.com/thing")


def test_is_governed(example):
    assert fp.is_governed(example) is True
    ungoverned = copy.deepcopy(example)
    ungoverned.pop("iaiso")
    assert fp.is_governed(ungoverned) is False


def test_posture_empty_for_ungoverned(example):
    ungoverned = copy.deepcopy(example)
    ungoverned.pop("iaiso")
    assert fp.posture(ungoverned) == {}


def example_addr() -> str:
    return json.loads(EXAMPLE.read_text())["identity"]["address"]
