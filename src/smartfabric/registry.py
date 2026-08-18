"""The fabric registry — the discovery + fleet-aggregation service.

docs/04 names the registry as a core fabric service: "every node self-registers on
start, deregisters on drain." Until now it was described but not built. This is a
real, dependency-free registry:

  - a node POSTs its fingerprint to /register with a health TTL;
  - it refreshes with a heartbeat, or is dropped when the TTL lapses (drain);
  - /nodes lists the currently-live governed nodes;
  - /fleet queries each live node's pressure.sample and returns the
    topology-weighted P_fleet (Layer-3 ecosystem coupling) across the whole fleet.

This is what turns a pile of independent nodes into one measurable organism: the
registry is where "what is the pressure of the WHOLE system, and is any node about
to breach?" gets answered. It reuses the same wire codec, fingerprint posture, and
fleet math as the rest of the package — no new primitives.

Transport is the same HTTP/CIR-adjacent JSON as the node, and it can run under the
same mTLS context (registry.serve(..., ssl_context=)). gRPC and a HA control-plane
store remain the follow-on described in docs/04.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import fingerprint as fp
from .pressure import NodeSample, fleet_pressure
from .wire import decode, encode
from .models import CIRHeader, CIRMessage


DEFAULT_TTL = 30.0  # seconds a registration stays live without a heartbeat


class RegistryEntry:
    __slots__ = ("fingerprint", "url", "centrality", "expires_at", "registered_at")

    def __init__(self, fingerprint: dict[str, Any], url: str, centrality: float,
                 ttl: float, now: float) -> None:
        self.fingerprint = fingerprint
        self.url = url
        self.centrality = centrality
        self.registered_at = now
        self.expires_at = now + ttl

    def to_public(self) -> dict[str, Any]:
        ident = self.fingerprint.get("identity", {})
        return {
            "id": ident.get("id"),
            "address": ident.get("address"),
            "url": self.url,
            "centrality": self.centrality,
            "governed": fp.is_governed(self.fingerprint),
            "expires_in": round(self.expires_at - time.time(), 1),
        }


class FabricRegistry:
    """Thread-safe in-memory registry. Deterministic + unit-testable."""

    def __init__(self, ttl: float = DEFAULT_TTL, clock=time.time) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        self._lock = threading.Lock()
        self._ttl = ttl
        self._clock = clock

    def register(self, fingerprint: dict[str, Any], url: str,
                 centrality: float = 1.0, ttl: float | None = None) -> dict[str, Any]:
        errs = fp.validate(fingerprint)
        if errs:
            return {"error": {"code": "schema", "message": "invalid fingerprint",
                              "detail": errs[:5], "retriable": False}}
        ident = fingerprint.get("identity", {})
        node_id = ident.get("id")
        if not node_id:
            return {"error": {"code": "schema", "message": "fingerprint missing identity.id",
                              "retriable": False}}
        now = self._clock()
        with self._lock:
            self._entries[node_id] = RegistryEntry(
                fingerprint, url, centrality, ttl or self._ttl, now)
        return {"registered": True, "id": node_id, "ttl": ttl or self._ttl}

    def heartbeat(self, node_id: str, ttl: float | None = None) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            e = self._entries.get(node_id)
            if not e:
                return {"error": {"code": "policy", "message": "unknown node; register first",
                                  "retriable": True}}
            e.expires_at = now + (ttl or self._ttl)
        return {"ok": True, "id": node_id}

    def deregister(self, node_id: str) -> dict[str, Any]:
        with self._lock:
            existed = self._entries.pop(node_id, None) is not None
        return {"deregistered": existed, "id": node_id}

    def _live(self) -> list[RegistryEntry]:
        now = self._clock()
        with self._lock:
            # drop expired (drain) as a side effect of listing
            dead = [k for k, e in self._entries.items() if e.expires_at <= now]
            for k in dead:
                del self._entries[k]
            return list(self._entries.values())

    def nodes(self) -> list[dict[str, Any]]:
        return [e.to_public() for e in self._live()]

    def fleet(self, sampler=None) -> dict[str, Any]:
        """Query each live node's pressure and aggregate topology-weighted P_fleet.

        `sampler(url) -> float` is injectable for tests; by default it POSTs a
        pressure.sample to each node over HTTP.
        """
        sampler = sampler or _http_pressure_sample
        samples: list[NodeSample] = []
        unreachable: list[str] = []
        for e in self._live():
            ident = e.fingerprint.get("identity", {})
            node_id = ident.get("id", e.url)
            try:
                p = sampler(e.url)
                samples.append(NodeSample(node_id=node_id, pressure=p, centrality=e.centrality))
            except Exception:
                unreachable.append(node_id)
        fpr = fleet_pressure(samples)
        return {
            "P_fleet": fpr.value,
            "peak_node": fpr.peak_node,
            "peak_pressure": fpr.peak_pressure,
            "hot_nodes": fpr.hot_nodes,
            "n_nodes": len(samples),
            "unreachable": unreachable,
        }


def _http_pressure_sample(url: str, timeout: float = 3.0) -> float:
    msg = CIRMessage(
        header=CIRHeader(id="01REGISTRYSAMPLE0000000001", verb="pressure.sample",
                         verb_version="0.1", from_addr="iaiso://registry@fabric/pressure",
                         to_addr="iaiso://node@fabric/sample"),
        body={"schema_ref": "pressure.sample/1", "payload": {}},
    )
    req = urllib.request.Request(url.rstrip("/") + "/cir", data=encode(msg),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        reply = decode(resp.read())
    return float(reply.body.get("payload", {}).get("p", 0.0))


# --------------------------------------------------------------------------- #
# HTTP transport                                                              #
# --------------------------------------------------------------------------- #

def _make_handler(reg: FabricRegistry):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, obj: Any, status: int = 200):
            body = json.dumps(obj, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/health"):
                self._send({"ok": True, "service": "smartfabric-registry"})
            elif self.path == "/nodes":
                self._send({"nodes": reg.nodes()})
            elif self.path == "/fleet":
                self._send(reg.fleet())
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw) if raw else {}
            except Exception as exc:
                self._send({"error": f"bad json: {exc}"}, 400)
                return
            if self.path == "/register":
                self._send(reg.register(data.get("fingerprint", {}), data.get("url", ""),
                                        float(data.get("centrality", 1.0)),
                                        data.get("ttl")))
            elif self.path == "/heartbeat":
                self._send(reg.heartbeat(data.get("id", ""), data.get("ttl")))
            elif self.path == "/deregister":
                self._send(reg.deregister(data.get("id", "")))
            else:
                self._send({"error": "post to /register, /heartbeat, or /deregister"}, 404)

    return Handler


def serve(reg: FabricRegistry | None = None, host: str = "127.0.0.1", port: int = 8760,
          ssl_context=None):
    reg = reg or FabricRegistry()
    server = ThreadingHTTPServer((host, port), _make_handler(reg))
    if ssl_context is not None:
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    return server, reg


def serve_in_thread(reg: FabricRegistry | None = None, host: str = "127.0.0.1", port: int = 0,
                    ssl_context=None):
    server, reg = serve(reg, host, port, ssl_context=ssl_context)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    scheme = "https" if ssl_context is not None else "http"
    return server, reg, f"{scheme}://{host}:{server.server_address[1]}"


# --------------------------------------------------------------------------- #
# Client helper: a node self-registers with a registry                        #
# --------------------------------------------------------------------------- #

def register_with(registry_url: str, fingerprint: dict[str, Any], node_url: str,
                  centrality: float = 1.0, ttl: float | None = None,
                  timeout: float = 3.0) -> dict[str, Any]:
    payload = {"fingerprint": fingerprint, "url": node_url, "centrality": centrality}
    if ttl is not None:
        payload["ttl"] = ttl
    body = json.dumps(payload).encode()
    req = urllib.request.Request(registry_url.rstrip("/") + "/register", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())
