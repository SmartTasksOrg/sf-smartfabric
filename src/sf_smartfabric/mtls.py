"""Mutual TLS for fabric nodes.

The plain node speaks HTTP/JSON — fine for a demo or a trusted network, but a real
fabric authenticates *both* ends: the node proves who it is, and it only accepts
peers whose client certificate chains to a CA the fabric trusts. That is the wire
form of the IAIso trust boundary — "bounds cooperating nodes" becomes "cooperating
nodes present certs from the fabric CA."

This module builds the SSL contexts; `node.serve(...)` wraps its socket with the
server context, and `mtls_post()` / the live harness use the client context. Cert
issuance is out of scope for the protocol — use your PKI, or `scripts/gen_certs.sh`
for a self-contained demo CA.

Stdlib `ssl` only; no dependencies.
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from typing import Any

from .models import CIRMessage
from .wire import decode, encode


def server_ssl_context(certfile: str, keyfile: str, cafile: str | None = None,
                       require_client_cert: bool = True) -> ssl.SSLContext:
    """Server side. With a CA and require_client_cert=True this is full mTLS:
    the node presents its cert AND demands a client cert chaining to `cafile`."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if cafile and require_client_cert:
        ctx.load_verify_locations(cafile)
        ctx.verify_mode = ssl.CERT_REQUIRED  # reject peers without a trusted client cert
    else:
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def client_ssl_context(cafile: str, certfile: str | None = None,
                       keyfile: str | None = None) -> ssl.SSLContext:
    """Client side. Verifies the node's server cert against `cafile`; if a client
    cert/key are given, presents them (the mutual half of mTLS)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cafile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False  # demo certs use a fixed CN, not a resolvable host
    ctx.verify_mode = ssl.CERT_REQUIRED
    if certfile and keyfile:
        ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return ctx


def mtls_post(url: str, msg: CIRMessage, ctx: ssl.SSLContext, timeout: float = 5.0) -> dict[str, Any]:
    """POST a CIR message to a node over (m)TLS and return the reply payload."""
    req = urllib.request.Request(url.rstrip("/") + "/cir", data=encode(msg),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        reply = decode(resp.read())
    return reply.body.get("payload", {})
