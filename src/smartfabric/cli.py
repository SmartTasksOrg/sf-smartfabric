"""Command-line entry point for SmartFabric.

    smartfabric --demo                 # offline tour (works the second you clone)
    smartfabric --version
    smartfabric validate <fp.json>     # schema-validate a node fingerprint
    smartfabric conformance <fp.json>  # run the FAB-* suite, print/emit a report
    smartfabric fleet <fleet.json>     # compute topology-weighted fleet pressure
"""
from __future__ import annotations

import argparse
import json
import sys

from . import conformance
from ._version import __version__
from .fingerprint import load, validate
from .pressure import NodeSample, fleet_pressure


def _cmd_validate(args: argparse.Namespace) -> int:
    fp = load(args.path)
    errors = validate(fp)
    if not errors:
        print(f"✓ {args.path}: schema-valid fingerprint")
        return 0
    print(f"✗ {args.path}: {len(errors)} schema error(s):", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def _cmd_conformance(args: argparse.Namespace) -> int:
    fp = load(args.path)
    report = conformance.run(fp)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for c in report.checks:
            mark = {"pass": "✓", "fail": "✗", "skip": "·"}[c.result.value]
            detail = f"  — {c.detail}" if c.detail else ""
            print(f"{mark} {c.id} [{c.level.value}] {c.title}{detail}")
        counts = report.summary()
        print(f"\n{'PASS' if report.passed else 'FAIL'}  "
              f"({counts['pass']} pass / {counts['fail']} fail / {counts['skip']} skip)")
        print(f"signature: {report.signature}")
    return 0 if report.passed else 1


def _cmd_fleet(args: argparse.Namespace) -> int:
    data = load(args.path)
    et = data.get("escalation_threshold", 0.85)
    samples = [NodeSample(**n) for n in data.get("nodes", [])]
    result = fleet_pressure(samples, escalation_threshold=et)
    out = {
        "fleet": data.get("fleet"),
        "P_fleet": round(result.value, 6),
        "peak_node": result.peak_node,
        "peak_pressure": result.peak_pressure,
        "hot_nodes": result.hot_nodes,
    }
    print(json.dumps(out, indent=2))
    return 0


def _cmd_vectors(args: argparse.Namespace) -> int:
    from . import vectors as vec
    results = vec.run_all()
    fails = 0
    for r in results:
        mark = "OK " if r.ok else "XX "
        if not r.ok:
            fails += 1
        print(f"{mark}{r.family:9} {r.name:28} {r.detail}")
    s = vec.summarize(results)
    print("---")
    print(f"pass={s['pass']} fail={s['fail']}")
    return 0 if fails == 0 else 2


def _cmd_serve(args: argparse.Namespace) -> int:
    from .node import serve
    ctx = None
    scheme = "http"
    if args.tls_cert and args.tls_key:
        from .mtls import server_ssl_context
        ctx = server_ssl_context(args.tls_cert, args.tls_key, args.tls_ca,
                                 require_client_cert=bool(args.tls_ca) and not args.no_client_cert)
        scheme = "https"
    server, node = serve(host=args.host, port=args.port, ssl_context=ctx)
    addr = server.server_address
    mode = "mTLS" if (ctx is not None and args.tls_ca and not args.no_client_cert) else \
           ("TLS" if ctx is not None else "plaintext")
    print(f"smartfabric node listening on {scheme}://{addr[0]}:{addr[1]}  ({mode}; POST CIR to /cir)")
    print(f"node identity: {node.fingerprint['identity']['address']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()
    return 0


def _cmd_live(args: argparse.Namespace) -> int:
    from . import live
    if args.url:
        results = live.run(args.url)
    else:
        results = live.run_spawned()
    fails = 0
    for r in results:
        mark = "✓" if r.ok else "✗"
        if not r.ok:
            fails += 1
        detail = f"  — {r.detail}" if r.detail else ""
        print(f"{mark} {r.id} {r.title}{detail}")
    s = live.summarize(results)
    print(f"\n{'PASS' if fails == 0 else 'FAIL'}  ({s['pass']} pass / {s['fail']} fail)")
    return 0 if fails == 0 else 2


def _cmd_registry(args: argparse.Namespace) -> int:
    from .registry import serve
    ctx = None
    scheme = "http"
    if args.tls_cert and args.tls_key:
        from .mtls import server_ssl_context
        ctx = server_ssl_context(args.tls_cert, args.tls_key, args.tls_ca,
                                 require_client_cert=bool(args.tls_ca) and not args.no_client_cert)
        scheme = "https"
    server, reg = serve(host=args.host, port=args.port, ssl_context=ctx)
    addr = server.server_address
    print(f"smartfabric registry on {scheme}://{addr[0]}:{addr[1]}  "
          f"(POST /register /heartbeat /deregister; GET /nodes /fleet)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smartfabric",
        description="IAIso Fabric Protocol (IFP) reference tools.",
    )
    p.add_argument("--version", action="version", version=f"smartfabric {__version__}")
    p.add_argument("--demo", action="store_true", help="run the offline demo and exit")

    sub = p.add_subparsers(dest="command")

    v = sub.add_parser("validate", help="schema-validate a node fingerprint")
    v.add_argument("path")
    v.set_defaults(func=_cmd_validate)

    c = sub.add_parser("conformance", help="run the FAB-* conformance suite")
    c.add_argument("path")
    c.add_argument("--json", action="store_true", help="emit the report as JSON")
    c.set_defaults(func=_cmd_conformance)

    f = sub.add_parser("fleet", help="compute topology-weighted fleet pressure")
    f.add_argument("path")
    f.set_defaults(func=_cmd_fleet)

    x = sub.add_parser("vectors", help="run the behavioral conformance vectors")
    x.set_defaults(func=_cmd_vectors)

    s = sub.add_parser("serve", help="run a live IFP node (HTTP/CIR transport)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8770)
    s.add_argument("--tls-cert", default=None, help="server certificate (PEM) — enables TLS")
    s.add_argument("--tls-key", default=None, help="server private key (PEM)")
    s.add_argument("--tls-ca", default=None, help="CA to verify client certs — enables mTLS")
    s.add_argument("--no-client-cert", action="store_true",
                   help="with --tls-ca set, serve TLS without requiring a client cert")
    s.set_defaults(func=_cmd_serve)

    l = sub.add_parser("live", help="run the live FAB-L-* harness against a node")
    l.add_argument("--url", default=None, help="node URL; omit to spawn one in-process")
    l.set_defaults(func=_cmd_live)

    r = sub.add_parser("registry", help="run the fabric registry (discovery + fleet aggregation)")
    r.add_argument("--host", default="127.0.0.1")
    r.add_argument("--port", type=int, default=8760)
    r.add_argument("--tls-cert", default=None, help="server certificate (PEM) — enables TLS")
    r.add_argument("--tls-key", default=None, help="server private key (PEM)")
    r.add_argument("--tls-ca", default=None, help="CA to verify client certs — enables mTLS")
    r.add_argument("--no-client-cert", action="store_true",
                   help="with --tls-ca set, serve TLS without requiring a client cert")
    r.set_defaults(func=_cmd_registry)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        from .demo import run
        return run()
    if getattr(args, "func", None):
        return args.func(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
