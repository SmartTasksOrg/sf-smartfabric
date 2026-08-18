"""Live node + transport tests — spins up a real node in-process and drives it."""
import json
import urllib.request

import pytest

from smartfabric import live
from smartfabric.models import CIRHeader, CIRMessage
from smartfabric.node import FabricNode, serve_in_thread
from smartfabric.wire import decode, encode


@pytest.fixture
def running_node():
    server, node, url = serve_in_thread()
    yield node, url
    server.shutdown()


def _post(url, verb, token=None, payload=None):
    msg = CIRMessage(
        header=CIRHeader(id="01TESTLIVE0000000000000001", verb=verb, verb_version="0.1",
                         from_addr="iaiso://t@local/x", to_addr="iaiso://n@local/y"),
        body={"schema_ref": f"{verb}/1", "payload": payload or {}},
        auth={"token": token} if token else {},
    )
    req = urllib.request.Request(url + "/cir", data=encode(msg), method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return decode(r.read()).body["payload"]


def test_health_endpoint(running_node):
    _node, url = running_node
    with urllib.request.urlopen(url + "/health", timeout=5) as r:
        assert json.loads(r.read())["ok"] is True


def test_describe_returns_fingerprint(running_node):
    _node, url = running_node
    p = _post(url, "describe")
    assert "fingerprint" in p and "iaiso" in p["fingerprint"]


def test_invoke_without_consent_denied(running_node):
    _node, url = running_node
    p = _post(url, "invoke", payload={"tokens": 1000})
    assert p["error"]["code"] == "policy"
    assert "consent" in p["error"]["message"].lower()


def test_invoke_with_consent_advances_pressure(running_node):
    _node, url = running_node
    p = _post(url, "invoke", token="jwt", payload={"tokens": 20000, "tool_calls": 2})
    assert p["accepted"] is True
    assert p["p"] > 0


def test_halt_blocks_expansion(running_node):
    _node, url = running_node
    _post(url, "halt.global")
    p = _post(url, "invoke", token="jwt", payload={"tokens": 1000})
    assert p["error"]["code"] == "policy"
    assert "halt" in p["error"]["message"].lower()


def test_full_live_harness_passes():
    # the whole FAB-L-* suite against a freshly spawned node
    results = live.run_spawned()
    failures = [f"{r.id}: {r.detail}" for r in results if not r.ok]
    assert not failures, failures
    assert len(results) == 6
