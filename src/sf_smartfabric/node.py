"""A runnable IFP node — the transport layer (roadmap Iteration 2/5).

Until now the repo had the *contract* (fingerprint, CIR envelope, pressure model,
vectors) but no running service. This is a real, dependency-free node: a stdlib
HTTP server that speaks CIR over the wire and actually *enforces* the containment
semantics — consent-gated expansion (invariant 4), clocked pressure, atomic
release (invariant 2), and a Layer-6 global halt.

Over HTTP a message is one-per-request (docs/01 §4: one message per unit on
HTTP), so the request body is the canonical-JSON CIR envelope and the response is
a canonical-JSON CIR envelope. No framing prefix on HTTP.

This is what deployments run and what integrations point at. It is intentionally
minimal — no gRPC/mTLS/registry yet (those remain follow-on fabric services in
docs/04). It is enough to drive a *behavioural* conformance harness (live.py),
which is the milestone this closes: proving enforcement over the wire, not just
computing vectors.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .models import CIRHeader, CIRMessage, EXPANDING_VERBS
from .pressure import PressureConfig, PressureEngine
from .wire import decode, encode
from . import fingerprint as fp

# Closed error taxonomy (docs/01 §12): transport/auth/policy/schema/capacity/internal
ERR_AUTH = "auth"
ERR_POLICY = "policy"
ERR_SCHEMA = "schema"
ERR_CAPACITY = "capacity"


class FabricNode:
    """The node's behaviour, independent of transport. Deterministic + testable."""

    def __init__(self, fingerprint: dict[str, Any] | None = None,
                 config: PressureConfig | None = None) -> None:
        self.fingerprint = fingerprint or _default_fingerprint()
        post = fp.posture(self.fingerprint).get("pressure", {})
        cfg = config or _config_from_posture(post)
        self.engine = PressureEngine(cfg)
        consent = fp.posture(self.fingerprint).get("consent", {})
        self.scope_required = bool(consent.get("scope_required", True))
        self.halted = False
        self.provenance: list[dict[str, Any]] = []
        self._prev_p = 0.0
        self._addr = self.fingerprint.get("identity", {}).get("address", "iaiso://node@local/")

    # -- verb handlers ----------------------------------------------------- #

    def handle(self, msg: CIRMessage) -> CIRMessage:
        verb = msg.header.verb
        self.provenance.append({"verb": verb, "id": msg.header.id})

        if self.halted and verb not in ("describe", "pressure.sample"):
            return self._err(msg, ERR_POLICY, "node is under a Layer-6 global halt", retriable=False)

        if verb == "describe":
            return self._reply(msg, {"fingerprint": self.fingerprint})
        if verb == "pressure.sample":
            return self._reply(msg, self._sample())
        if verb == "halt.global":
            self.halted = True
            return self._reply(msg, {"halted": True})
        if verb == "reset":
            self.engine.reset()
            self._prev_p = 0.0
            return self._reply(msg, {"reset": True})
        if verb == "provenance.emit":
            return self._reply(msg, {"recorded": True, "count": len(self.provenance)})
        if verb in EXPANDING_VERBS:
            return self._handle_expanding(msg)
        # known-but-unhandled or unknown -> schema error
        return self._err(msg, ERR_SCHEMA, f"verb not handled by this node: {verb}", retriable=False)

    def _handle_expanding(self, msg: CIRMessage) -> CIRMessage:
        # Invariant 4: consent-bounded expansion. Default deny without a token.
        if self.scope_required and not msg.has_consent():
            return self._err(msg, ERR_POLICY,
                             "expanding verb requires a ConsentScope (invariant 4: default deny)",
                             retriable=False)
        if self.engine.locked:
            return self._err(msg, ERR_CAPACITY,
                             "node is post-release locked; reset required (invariant 2)",
                             retriable=True)
        payload = msg.body.get("payload", {}) if isinstance(msg.body, dict) else {}
        out = self.engine.step(
            tokens=int(payload.get("tokens", 20000)),
            tool_calls=int(payload.get("tool_calls", 2)),
            depth=int(payload.get("depth", 0)),
        )
        result = {
            "accepted": True,
            "p": out.pressure,
            "zone": out.zone.value,
            "released": out.released,
            "locked": out.locked,
        }
        # escalation zone is a Layer-4 event the fabric would broker; we surface it
        if out.zone.value == "escalation":
            result["escalation"] = True
            result["required_authorizers"] = fp.posture(self.fingerprint).get("multi_party_auth", 2)
        return self._reply(msg, result)

    def _sample(self) -> dict[str, Any]:
        p = self.engine.pressure
        dpdt = p - self._prev_p
        self._prev_p = p
        return {"p": p, "dpdt": dpdt, "zone": self.engine.zone().value, "locked": self.engine.locked}

    # -- envelope helpers -------------------------------------------------- #

    def _reply(self, req: CIRMessage, payload: dict[str, Any]) -> CIRMessage:
        return CIRMessage(
            header=CIRHeader(
                id=req.header.id,
                verb=req.header.verb,
                from_addr=self._addr,
                to_addr=req.header.from_addr,
                verb_version=req.header.verb_version,
            ),
            body={"schema_ref": f"{req.header.verb}.result/1", "payload": payload},
        )

    def _err(self, req: CIRMessage, code: str, message: str, *, retriable: bool) -> CIRMessage:
        return CIRMessage(
            header=CIRHeader(
                id=req.header.id,
                verb=req.header.verb,
                from_addr=self._addr,
                to_addr=req.header.from_addr,
                verb_version=req.header.verb_version,
            ),
            body={"schema_ref": "error/1",
                  "payload": {"error": {"code": code, "message": message, "retriable": retriable}}},
        )


# --------------------------------------------------------------------------- #
# HTTP transport                                                             #
# --------------------------------------------------------------------------- #

def _make_handler(node: FabricNode):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence
            pass

        def _send(self, obj_bytes: bytes, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(obj_bytes)))
            self.end_headers()
            self.wfile.write(obj_bytes)

        def do_GET(self):
            if self.path in ("/", "/health"):
                self._send(b'{"ok":true,"service":"smartfabric-node"}')
            else:
                self._send(b'{"error":"not found"}', 404)

        def do_POST(self):
            if self.path != "/cir":
                self._send(b'{"error":"post CIR messages to /cir"}', 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                msg = decode(raw)
            except Exception as exc:
                self._send(json.dumps({"error": f"bad CIR: {exc}"}).encode(), 400)
                return
            reply = node.handle(msg)
            self._send(encode(reply))

    return Handler


def serve(node: FabricNode | None = None, host: str = "127.0.0.1", port: int = 8770,
          ssl_context=None):
    node = node or FabricNode()
    server = ThreadingHTTPServer((host, port), _make_handler(node))
    if ssl_context is not None:
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server, node


def serve_in_thread(node: FabricNode | None = None, host: str = "127.0.0.1", port: int = 0,
                    ssl_context=None):
    """Start a node on an ephemeral port in a daemon thread. Returns (server, node, url).
    Used by the live harness and tests — no external orchestration needed."""
    server, node = serve(node, host, port, ssl_context=ssl_context)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    actual_port = server.server_address[1]
    scheme = "https" if ssl_context is not None else "http"
    return server, node, f"{scheme}://{host}:{actual_port}"


# --------------------------------------------------------------------------- #
# Defaults                                                                    #
# --------------------------------------------------------------------------- #

def _config_from_posture(post: dict[str, Any]) -> PressureConfig:
    if not post:
        return PressureConfig()
    return PressureConfig(
        escalation_threshold=post.get("escalation_threshold", 0.85),
        release_threshold=post.get("release_threshold", 0.95),
        dissipation_per_step=post.get("dissipation_per_step", 0.02),
        token_coefficient=post.get("token_coefficient", 0.015),
        tool_coefficient=post.get("tool_coefficient", 0.08),
        depth_coefficient=post.get("depth_coefficient", 0.05),
        post_release_lock=post.get("post_release_lock", True),
    )


def _default_fingerprint() -> dict[str, Any]:
    """A minimal governed fingerprint so a bare `serve()` is conformant."""
    return {
        "iaiso_version": "0.1",
        "identity": {"id": "01LIVE0000000000000000NODE", "address": "iaiso://live-node@local/demo",
                     "public_key": "ed25519:demo"},
        "ports": [{"number": 8770, "transport": "tcp", "binding": "http2",
                   "tls": "none", "plane": "data", "direction": "listen"}],
        "standards": {"identity": ["mtls"], "crypto": ["tls1.3"],
                      "observability": ["otel-traces"], "governance": ["provenance/1"]},
        "cir": {"verbs": [{"verb": "describe", "version": "0.1"},
                          {"verb": "invoke", "version": "0.1"},
                          {"verb": "pressure.sample", "version": "0.1"},
                          {"verb": "consent.assert", "version": "0.1"},
                          {"verb": "halt.global", "version": "0.1"}],
                "mapping": []},
        "placement": {"l8_jurisdiction": {"country": "US", "egress": "open"}},
        "contract": {"delivery": "at-least-once", "audit_level": "standard"},
        "iaiso": {"framework_version": "5.0", "enforced_layers": [1, 2, 4, 5, 6],
                  "pressure": {"escalation_threshold": 0.85, "release_threshold": 0.95,
                               "clock_ms": 1000},
                  "consent": {"issuer": "https://consent.local", "scope_required": True},
                  "reset": {"lossy": True}, "invariants_attested": [2, 3, 4]},
    }
