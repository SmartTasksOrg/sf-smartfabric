"""mTLS transport tests — a node can require a client cert and refuse peers without one."""
import subprocess
import sys
from pathlib import Path

import pytest

from smartfabric.models import CIRHeader, CIRMessage


def _describe():
    return CIRMessage(
        header=CIRHeader(id="01MTLS0000000000000000TEST", verb="describe", verb_version="0.1",
                         from_addr="iaiso://h@local/x", to_addr="iaiso://n@local/y"),
        body={"schema_ref": "describe/1", "payload": {}},
    )


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    d = tmp_path_factory.mktemp("certs")
    script = Path(__file__).resolve().parents[1] / "scripts" / "gen_certs.sh"
    r = subprocess.run(["bash", str(script), str(d), "client-a"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not (d / "ca.crt").exists():
        pytest.skip(f"openssl/cert generation unavailable: {r.stderr}")
    return d


def test_mtls_requires_client_cert(certs):
    from smartfabric.mtls import server_ssl_context, client_ssl_context, mtls_post
    from smartfabric.node import serve_in_thread

    sctx = server_ssl_context(str(certs / "server.crt"), str(certs / "server.key"),
                              str(certs / "ca.crt"), require_client_cert=True)
    server, _node, url = serve_in_thread(ssl_context=sctx)
    try:
        # trusted client cert -> allowed
        ok_ctx = client_ssl_context(str(certs / "ca.crt"),
                                    str(certs / "client-a.crt"), str(certs / "client-a.key"))
        payload = mtls_post(url, _describe(), ok_ctx)
        assert "fingerprint" in payload

        # no client cert -> refused at TLS layer
        no_cert = client_ssl_context(str(certs / "ca.crt"))
        with pytest.raises(Exception):
            mtls_post(url, _describe(), no_cert)
    finally:
        server.shutdown()
