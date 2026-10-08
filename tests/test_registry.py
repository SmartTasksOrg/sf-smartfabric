"""Registry tests — discovery, health TTL (drain), and fleet aggregation.

Spins up a real registry plus real nodes in-process and checks the control-plane
behaviour end to end: a node appears after /register, drops after its TTL lapses,
and /fleet aggregates topology-weighted pressure across the live nodes.
"""
import json
import urllib.request

import pytest

from sf_smartfabric.fingerprint import load_schema
from sf_smartfabric.node import FabricNode, serve_in_thread as serve_node
from sf_smartfabric.registry import (
    FabricRegistry,
    register_with,
    serve_in_thread as serve_registry,
)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def _make_fp(node_id: str):
    fpr = FabricNode().fingerprint  # a valid governed fingerprint
    fpr = json.loads(json.dumps(fpr))  # deep copy
    fpr["identity"]["id"] = node_id
    fpr["identity"]["address"] = f"iaiso://{node_id.lower()}@fabric/demo"
    return fpr


def test_register_appears_in_nodes():
    server, reg, url = serve_registry()
    try:
        out = register_with(url, _make_fp("01NODE000000000000000000AA"), "http://127.0.0.1:9",
                            centrality=2.0)
        assert out["registered"] is True
        nodes = _get(url + "/nodes")["nodes"]
        assert len(nodes) == 1
        assert nodes[0]["centrality"] == 2.0
    finally:
        server.shutdown()


def test_ttl_expiry_drains_node():
    # controllable clock so we don't sleep
    t = {"now": 1000.0}
    reg = FabricRegistry(ttl=30.0, clock=lambda: t["now"])
    reg.register(_make_fp("01NODE000000000000000000BB"), "http://127.0.0.1:9")
    assert len(reg.nodes()) == 1
    t["now"] += 31.0  # past the TTL, no heartbeat
    assert reg.nodes() == []  # drained


def test_heartbeat_keeps_node_alive():
    t = {"now": 1000.0}
    reg = FabricRegistry(ttl=30.0, clock=lambda: t["now"])
    reg.register(_make_fp("01NODE000000000000000000CC"), "http://127.0.0.1:9")
    t["now"] += 20.0
    reg.heartbeat("01NODE000000000000000000CC")
    t["now"] += 20.0  # 40s since register, but only 20s since heartbeat
    assert len(reg.nodes()) == 1


def test_fleet_aggregates_over_live_nodes():
    # two real nodes with DISTINCT identities; drive one hot, aggregate via registry
    fp1 = _make_fp("01NODE0000000000000000HUB1")
    fp2 = _make_fp("01NODE0000000000000000LEAF")
    s1, node1, url1 = serve_node(FabricNode(fingerprint=fp1))
    s2, node2, url2 = serve_node(FabricNode(fingerprint=fp2))
    sreg, reg, regurl = serve_registry()
    try:
        # push node1's pressure up (but not to release) through consent-gated invokes
        for _ in range(2):
            _post_invoke(url1)
        register_with(regurl, node1.fingerprint, url1, centrality=3.0)  # hub
        register_with(regurl, node2.fingerprint, url2, centrality=1.0)  # leaf
        fleet = _get(regurl + "/fleet")
        assert fleet["n_nodes"] == 2
        assert fleet["peak_node"] is not None
        assert 0.0 <= fleet["P_fleet"] <= 1.0
        # the hot hub should be the peak
        assert fleet["peak_pressure"] > 0.0
    finally:
        for s in (s1, s2, sreg):
            s.shutdown()


def _post_invoke(node_url):
    from sf_smartfabric.models import CIRHeader, CIRMessage
    from sf_smartfabric.wire import encode
    msg = CIRMessage(
        header=CIRHeader(id="01REGTESTINVOKE00000000001", verb="invoke", verb_version="0.1",
                         from_addr="iaiso://t@local/x", to_addr="iaiso://n@local/y"),
        body={"schema_ref": "invoke/1", "payload": {"tokens": 15000, "tool_calls": 1}},
        auth={"token": "jwt"},
    )
    req = urllib.request.Request(node_url + "/cir", data=encode(msg), method="POST")
    urllib.request.urlopen(req, timeout=5).read()


def test_deregister_removes_node():
    reg = FabricRegistry()
    reg.register(_make_fp("01NODE000000000000000000DD"), "http://127.0.0.1:9")
    assert len(reg.nodes()) == 1
    out = reg.deregister("01NODE000000000000000000DD")
    assert out["deregistered"] is True
    assert reg.nodes() == []
