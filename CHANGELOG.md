# Changelog

All notable changes to SmartFabric (the IAIso Fabric Protocol reference).

## Unreleased

## 0.5.1

### Fixed
- A PyPI install could not run `sf-smartfabric --demo`, `sf-smartfabric vectors` or fingerprint validation: the files
  they read (`schema/`, `examples/`, `spec/vectors/`) were not in the wheel, and the lookup used the distribution name
  `sf-smartfabric` instead of the package `sf_smartfabric`. The wheel now carries identical copies under
  `sf_smartfabric/data/` (a test fails if a copy differs from its source) and one helper reads them, from a PyPI
  install or a clone. A new CI job installs the built wheel in a clean environment and runs all three from an empty folder.

### Documentation
- README "Install": `pip install sf-smartfabric` now that the first release is on PyPI, with how to check its provenance;
  "Status" says where it is published. `names.json` marks `sf-smartfabric` as registered.
- `publish/server.json` (the MCP registry manifest) is back under its normal name; it is not submitted to the registry yet.
- Release check: the wheel installed in a clean environment now runs the README's demo command from an empty folder, not only `--version`.

## 0.5.0 — first PyPI release as `sf-smartfabric` (2026-10-09)

Published to PyPI on 2026-10-09 from tag `v0.5.0` by `.github/workflows/release.yml`, with provenance attestations. The version number is the same as the 0.5.0 entry below; these are the changes made before that first upload.

### Security
- Install instructions no longer name packages the maintainers have not
  published. Until the first release, install from a clone (README, "Install").
- New `SECURITY.md` (private vulnerability reporting), `names.json` (the only
  official package names) and a CI check that fails when a document names any
  other package.
- Releases are built and published only by `.github/workflows/release.yml`
  through PyPI trusted publishing, with provenance attestations.

### Changed
- **Renamed (breaking), `sf-` = Smart Family:** repository `SmartTasksOrg/sf-smartfabric`, PyPI package `sf-smartfabric`, command `sf-smartfabric`, import package `sf_smartfabric`, MCP server `io.github.smarttasksorg/sf-smartfabric`. The unprefixed names are not used any more, so nobody can be sent to a look-alike.
- README: "Install" and "Status" sections; the old Status (v0.2.0) is replaced by the current state of 0.5.0.
- `pyproject.toml`: setuptools 77+, "3 - Alpha" classifier, Source/Issues/Security/Changelog URLs (licence unchanged).
- Deploy configs reference the image tag `0.5.0` instead of `latest`; the image is not published yet.
- Node port package `sf-smartfabric` (unpublished); Go module path `github.com/SmartTasksOrg/sf-smartfabric/ports/go`.
- The composite GitHub Action pins `actions/setup-python` by commit.
- `MARKETING.md` moved out of the public repository.

## [0.5.0] — 2026-08-17 · the registry, and docs that match the code
Adds the fabric registry (the last core service that was described but unbuilt),
and brings the documentation fully in sync with the shipped implementation.

### Added
- **Fabric registry** (`src/smartfabric/registry.py`): the discovery + fleet-
  aggregation service from docs/04. Nodes self-register (`register_with`), refresh
  via heartbeat, and are drained on TTL lapse. `GET /nodes` lists live nodes;
  `GET /fleet` queries each live node's pressure and returns the topology-weighted
  `P_fleet` (the pressure aggregator). Runs under the same optional mTLS as the
  node. `smartfabric registry` CLI command. Tested end to end (registration,
  discovery, TTL expiry, heartbeat, and fleet aggregation over real nodes).
- **docs/09 — Transport and Operations**: the node service, mTLS, the live
  `FAB-L-*` family, and the registry, all as runnable operations.
- **docs/10 — Deployment**: the one-image model and the full platform matrix
  (Docker/Compose/k8s/Helm/clouds/GPU providers), with the honest production posture.
- **CONTRIBUTING.md**: the conformance bar and how to add ports/targets.

### Changed
- `docs/04` now carries an implementation-status callout marking which reference-
  architecture services ship today (node, mTLS, registry, pressure aggregator,
  consent gate, reset/halt, conformance) versus what remains (gRPC, an HA control-
  plane store, the negotiator/router/policy services).
- README reading order includes docs/09 and docs/10; CLI gains `registry`.

### Still open (honest status)
- The registry is single-process/in-memory — correct and tested, but not yet the
  highly-available control-plane store of docs/04.
- Transport is HTTP/JSON + optional mTLS; a gRPC binding and the negotiator/router/
  policy services remain the follow-on fabric work.
- Go/PHP/Rust/Ruby/C# ports, the Docker image, and the k8s/Helm manifests are
  authored but not built/run in the sandbox (labelled in their READMEs).

## [0.4.0] — 2026-08-17 · mTLS, the full language family, and release automation
Hardens the transport with mutual TLS, completes the ten-language port family
(five now verified in CI), broadens the deploy matrix to Kubernetes/Helm and the
docker-image cloud + GPU providers, and adds the internal machinery that publishes
the public artifacts from the private monorepo.

### Added
- **Mutual TLS** (`src/smartfabric/mtls.py`): server/client SSL context builders;
  `serve(..., ssl_context=)` wraps the node socket; `smartfabric serve --tls-cert
  --tls-key --tls-ca` runs the node as mTLS (presents a cert AND requires a client
  cert chaining to the fabric CA). `scripts/gen_certs.sh` mints a demo PKI.
  End-to-end tested: cert-bearing client allowed, certless client refused at the
  TLS layer (`tests/test_mtls.py`).
- **Full language family** (`ports/`): added C++ and C (both verified in CI) and
  Ruby and C# (written + vector-checked). Five implementations now run in CI
  (Python, Node, Java, C++, C); five more ship (Go, PHP, Rust, Ruby, C#).
- **More platforms** (`deploy/`): Kubernetes manifests, a Helm chart (with an mTLS
  toggle), Fly.io, Render, DigitalOcean; and the **GPU providers vast.ai and
  RunPod** — all consuming the same container image. The node runs next to GPU
  model workers to govern them.
- **Release machinery** (`private/release/`): `build_docker.sh` / `publish_docker.sh`
  (GHCR + optional Docker Hub), `publish_pypi.sh`, `build_all_ports.sh`, and
  `publish_public.py` — the guarded publisher that extracts only the public
  `smartfabric/` subtree, runs the private-namespace + no-private-paths + smoke-test
  guards, and mirrors it to the public repo. `release.sh` orchestrates the whole
  flow (`--dry-run` / build / `--publish`).

### Changed
- CLI `serve` gains TLS/mTLS flags.
- Interop harness compiles and runs C/C++ where a toolchain exists.

### Still open (honest status)
- Go/PHP/Rust/Ruby/C# ports, the Docker image, and the k8s/Helm manifests are
  authored but not executed/built in the sandbox (no toolchain/daemon there);
  labelled as such in `ports/README.md` and `deploy/README.md`.
- Cloud/GPU recipes reference a placeholder image tag that must be published first
  (that's exactly what `private/release/` does).
- Transport is HTTP/JSON + optional mTLS; gRPC and the registry remain follow-on
  fabric services (`docs/04`).

## [0.3.0] — 2026-08-17 · transport, breadth, and deployability
Adds a real running node (roadmap Iteration 2/5) so containment is enforced *over
the wire*, broadens conformance to more languages, and makes the node deployable
and embeddable in agent toolchains.

### Added
- **Node service / transport layer** (`src/smartfabric/node.py`): a dependency-free
  HTTP/CIR node (`smartfabric serve`) that actually enforces the semantics —
  consent-gated expansion (invariant 4, default deny), clocked pressure, atomic
  release+reset (invariant 2), and a Layer-6 global halt. One CIR message per
  request over HTTP; canonical-JSON in and out.
- **Live conformance** (`src/smartfabric/live.py`): `FAB-L-*` checks that drive a
  running node over HTTP and assert real behaviour (denial without consent,
  escalation under load, atomic release, halt blocking expansion). `smartfabric live`
  runs them against an in-process node with no orchestration.
- **More independent ports** (`ports/`): Java (runnable, verified in CI) plus Go,
  PHP, and Rust (written + vector-checked; run in your own environment). The
  interop harness now agrees across Python + Node + Java.
- **Toolchain integrations** (`integrations/`): LangChain callback, n8n Function
  node, Flowise custom tool, and a GitHub Action — thin adapters that meter a call
  and relay the node's verdict, turning containment into a live guardrail.
- **Deployments** (`deploy/`): Dockerfile + a two-node docker-compose fabric, and
  GCP (Terraform + cloud-init), AWS (EC2 user-data), and Azure (cloud-init) recipes
  for the node service.

### Changed
- CLI gains `serve` and `live` subcommands.
- CI now runs the live harness and the Python+Node+Java interop harness.

### Still open (honest status)
- Transport is minimal HTTP/JSON — no gRPC/mTLS/registry yet (those remain the
  follow-on fabric services in `docs/04`).
- Go/PHP/Rust ports and the Docker image are authored but not executed in the build
  sandbox (no toolchain/daemon there); they're labelled as such in `ports/README.md`
  and `deploy/README.md`.
- Cloud recipes reference a placeholder container tag you must publish first.

## [0.2.0] — 2026-08-17 · from draft to protocol
Closes the three gaps that kept v0.1 a draft: a frozen wire format, a second
independent interoperable implementation, and behavioural (not declarative)
conformance.

### Added
- **Frozen wire format** (`docs/08_WIRE_FORMAT.md`):
  - Canonical-JSON encoding rules (deterministic, byte-stable, hashable) —
    reference in `src/smartfabric/wire.py`.
  - LEB128 varint length-delimited framing.
  - `proto/fabric.proto` — the binary contract with **frozen field numbers** and
    the closed `Verb` enum.
  - Versioning/compatibility rules (`wire_version` + per-verb semver ranges).
- **Behavioural conformance vectors** (`spec/vectors/*.json`): pinned inputs →
  outputs for pressure trajectories, fleet aggregation, and envelope
  encoding/framing. `smartfabric vectors` runs them; `tools/gen_vectors.py`
  regenerates from the reference.
- **Second independent implementation** (`ports/node/`): a from-spec Node.js port
  of the pressure engine, fleet aggregation, and canonical-JSON wire format.
  `ports/conformance/run.sh` runs both implementations against the shared vectors
  and requires agreement — including **byte-exact** canonical-JSON + sha256 +
  framing across the two independent serializers.
- New tests: `tests/test_wire_vectors.py` (public suite now 47 tests).

### Changed
- `schema/example.fingerprint.json` and `docs/07` pressure fields already track
  the real IAIso v5.0 core; docs/06 now documents the static-vs-behavioural split
  and the two-implementation bar.

### Still open (honestly)
- **Live/behavioural harness against a running node** (drive endpoints, observe
  real enforcement) — the vectors prove computation; a network-level harness is
  the next step.
- **Protobuf binary interop** is field-number-frozen but not run here (no
  `protoc` in the build sandbox); canonical JSON is the exercised baseline.
- Report signatures are still content digests (`sha256:`) pending ed25519.
- Pressure defaults remain the core's reference values, not calibrated.

## [0.1.0] — 2026-08-17
### Added
- Initial specification draft (docs 00–07), grounded on IAIso v5.0 core.
- `schema/fingerprint.schema.json` — the node contract, with the `iaiso`
  containment posture block bound to the core's real pressure field names.
- `schema/conformance-report.schema.json` — the signed report shape.
- Runnable reference (`src/smartfabric/`): pressure engine + fleet aggregation,
  CIR envelope, fingerprint validation, `FAB-*` static conformance, CLI + demo.
- Public test suite (27 tests, offline).
