# 09 — Transport and operations

Docs 00–08 define the *protocol*. This doc covers the *running system*: the node
service, the wire transport, mutual TLS, the live conformance family, and the
registry. Everything here is implemented and runnable in this repo — it is the
operational counterpart to the spec.

## 9.1 The node service

A node is a process that speaks CIR over a transport and enforces the containment
mechanics locally. The reference node is `src/sf_smartfabric/node.py` — a dependency-
free HTTP service.

```
sf-smartfabric serve --host 0.0.0.0 --port 8770
```

Endpoints:

| Method / path | Purpose |
| --- | --- |
| `GET /health` | liveness — `{"ok": true, "service": "smartfabric-node"}` |
| `POST /cir` | one CIR message in the body → one CIR message reply |

Over HTTP a message is **one per request** (docs/01 §4), so there is no framing
prefix on the wire here — the request body is the canonical-JSON envelope and the
response is a canonical-JSON envelope. (The LEB128 framing in docs/08 is for
stream transports that carry many messages over one connection.)

### What the node actually enforces

The node is not a passthrough. On every message it applies the same mechanics the
protocol defines:

- **Consent-gated expansion (invariant 4).** An expanding verb (`invoke`, `plan`,
  `stream.open`) with no ConsentScope is denied by default — a `policy` error, not
  a silent allow.
- **Clocked pressure.** Each accepted expanding verb advances the pressure model
  (tokens/tool-calls/depth intake minus dissipation); `pressure.sample` reports
  `{p, dpdt, zone}` without advancing it.
- **Atomic release + lock (invariant 2).** When pressure crosses the release
  threshold the node resets to zero and (by posture) post-release-locks until an
  explicit `reset`.
- **Layer-6 global halt.** After `halt.global`, every expanding verb is refused
  until the node is brought back.

### Verbs the reference node handles

`describe`, `pressure.sample`, `invoke` / `plan` / `stream.open` (expanding),
`halt.global`, `reset`, `provenance.emit`. Unknown or unhandled verbs return a
`schema` error. All errors use the closed taxonomy (docs/01 §12):
`transport | auth | policy | schema | capacity | internal`, each carrying a
`retriable` flag.

## 9.2 Mutual TLS

Plain HTTP/JSON is fine for a trusted network or a demo. For anything else — and
especially for shared/rented hosts (see docs/10, the GPU providers) — run the node
under mutual TLS. This is the wire form of the IAIso trust boundary: the node
presents its own certificate *and* refuses any peer whose client certificate does
not chain to a CA the fabric trusts.

```
scripts/gen_certs.sh certs client-a           # demo PKI: CA + server + client certs
sf-smartfabric serve \
  --tls-cert certs/server.crt \
  --tls-key  certs/server.key \
  --tls-ca   certs/ca.crt                      # requiring a client cert = mTLS
```

- `--tls-cert`/`--tls-key` alone → server-authenticated TLS.
- add `--tls-ca` → **mTLS** (client cert required, chaining to that CA).
- `--tls-ca ... --no-client-cert` → TLS with the CA present but client certs optional.

`src/sf_smartfabric/mtls.py` exposes `server_ssl_context()` / `client_ssl_context()`
and an `mtls_post()` helper. In Kubernetes/Helm, mount the certs from a Secret and
set `mtls.enabled=true` (docs/10). Use your real PKI (SPIFFE/SPIRE, a cloud CA) in
production; `gen_certs.sh` is a demo CA only.

## 9.3 Live conformance — the FAB-L family

Static `FAB-*` checks (docs/06) verify what a node *declares*; the behavioural
vectors verify what an implementation *computes*; the **FAB-L** live checks verify
what a running node actually *does* over the wire.

```
sf-smartfabric live                 # spawns a node in-process and drives it
sf-smartfabric live --url https://host:8770
```

| Check | Asserts |
| --- | --- |
| FAB-L-001 | `describe` returns a governed fingerprint |
| FAB-L-002 | an expanding verb without a ConsentScope is denied (invariant 4) |
| FAB-L-003 | an expanding verb with a ConsentScope advances pressure |
| FAB-L-004 | `pressure.sample` reports a valid `{p, dpdt, zone}` |
| FAB-L-005 | sustained load drives escalation, then atomic release + reset (invariant 2) |
| FAB-L-006 | after `halt.global`, further expansion is refused (Layer 6) |

A conformant node passes every FAB-L check. `--spawn`/no-`--url` runs the whole
family with no orchestration, which is what CI does.

## 9.4 The registry

A single node governs itself; the **registry** (`src/sf_smartfabric/registry.py`) is
what makes a *fleet* measurable as one organism. It is the discovery record store
docs/04 calls for: nodes self-register on start and are drained on TTL lapse.

```
sf-smartfabric registry --host 0.0.0.0 --port 8760
```

| Method / path | Purpose |
| --- | --- |
| `POST /register` | a node submits its fingerprint + URL (+ centrality, TTL) |
| `POST /heartbeat` | refresh a registration before its TTL lapses |
| `POST /deregister` | explicit drain |
| `GET /nodes` | list currently-live governed nodes |
| `GET /fleet` | query each live node's pressure and return topology-weighted `P_fleet` |

`/fleet` is the pressure aggregator from docs/04: it samples every live node and
runs the same `fleet_pressure()` used everywhere else, so a high-centrality hub
approaching release moves the fleet number more than a leaf. It reports the peak
node, the hot set (nodes in/above escalation), and any unreachable nodes.

A node can self-register on start with `registry.register_with(registry_url,
fingerprint, node_url)`; a heartbeat loop keeps it live; stopping the heartbeat
(or calling `/deregister`) drains it. The registry can also run under mTLS with the
same flags as the node.

### Honest limits of the registry today

It is a single-process, in-memory store — correct and testable, but not yet the
highly-available control plane of docs/04 (etcd/Consul-style). Persistence, HA, and
the negotiator/policy/router services are the remaining fabric work; the registry
here is the smallest useful version and the aggregation point the dynamics layer
(docs/05) needs.

## 9.5 Operating a small fabric

The minimal running fabric is: one registry + N nodes, each self-registering.

```
sf-smartfabric registry --port 8760 &
sf-smartfabric serve --port 8770 &          # node A (register it with the registry)
sf-smartfabric serve --port 8771 &          # node B
# ... each node POSTs /register to the registry, then heartbeats ...
curl localhost:8760/fleet                # topology-weighted P_fleet across the fleet
```

`deploy/docker-compose.yml` shows the containerised two-node version, and docs/10
covers every deployment target. For production, put the registry and nodes behind
mTLS, restrict exposure, and treat the registry as the fleet's pressure/discovery
control point.
