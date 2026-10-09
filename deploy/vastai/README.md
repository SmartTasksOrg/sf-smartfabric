# vast.ai (GPU) deploy

vast.ai is a GPU marketplace: you pick an offer and it runs a Docker image with an
on-start command. SmartFabric deploys there as the same node container.

## Why run the node on a GPU host

The node **governs** GPU-backed AI workers — it doesn't need the GPU itself. Running
it *next to* the model workers (same host / same pod) means the containment plane is
co-located with the compute it meters: pressure, consent-gating, and halt enforcement
sit right next to the thing being governed, with no extra network hop.

## Two ways to run it

**A. Use the published image.**
- Image: `ghcr.io/smarttasksorg/sf-smartfabric:0.5.0`
- On-start: `sf-smartfabric serve --host 0.0.0.0 --port 8770`
- Open port 8770 in the instance's port mappings (vast maps a public port to it).

**B. Use a CUDA base image you already run** (e.g. your model server) and add the
node as a sidecar process — paste `onstart.sh` into the on-start field; it installs
`sf-smartfabric` from PyPI if it isn't already present and runs the node.

## Verify

From your machine, against the public host:port vast assigned:

```
sf-smartfabric live --url http://<public-host>:<mapped-port>
```

## Honest scope

The node is plain HTTP/JSON here. On a rented GPU box that is inherently a shared,
untrusted environment — **turn on mTLS** (`--tls-cert/--tls-key/--tls-ca`, see
`scripts/gen_certs.sh` and `deploy/README.md`) and restrict the exposed port before
sending it anything real. The image is authored here but not built in this sandbox
(no Docker daemon) — build/publish it first (see `private/release/`).
