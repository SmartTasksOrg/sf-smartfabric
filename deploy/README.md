# deploy/ — running a fabric node

Everything here deploys the **node service** (`sf-smartfabric serve`) — a real HTTP/CIR
service that enforces IAIso containment (consent-gating, escalation, atomic release,
global halt, and optional mTLS). One container image, many targets.

## One image, every platform

The deployable unit is a single container. Build it once (`deploy/Dockerfile`),
publish it (see `private/release/`), then point any target below at the tag.

| Target | Files | Kind |
| --- | --- | --- |
| Docker | `Dockerfile` | one node container on :8770 with a `/health` check |
| Compose | `docker-compose.yml` | two-node fabric + one-shot live conformance |
| Kubernetes | `k8s/deployment.yaml` | Deployment + Service, readiness/liveness probes |
| Helm | `helm/` | parameterised chart (replicas, image, mTLS toggle) |
| GCP | `gcp/` | free-tier `e2-micro` VM (Terraform + cloud-init) |
| AWS | `aws/` | `t3.micro` EC2 (user-data) |
| Azure | `azure/` | `B1s` VM (cloud-init) |
| Fly.io | `fly/fly.toml` | image-based app with TLS handler |
| Render | `render/render.yaml` | image-based web service |
| DigitalOcean | `digitalocean/` | App Platform spec + plain Droplet |
| vast.ai (GPU) | `vastai/` | GPU marketplace, image + on-start |
| RunPod (GPU) | `runpod/` | GPU pod template |

The GPU targets (vast.ai, RunPod) run the node *next to* GPU-backed model workers so
the containment plane is co-located with the compute it governs — the node governs
GPU nodes, it doesn't need the GPU itself.

## Quick start (local)

```
docker build -f deploy/Dockerfile -t smartfabric-node ..
docker run -p 8770:8770 smartfabric-node
# or a two-node fabric + live conformance:
docker compose -f deploy/docker-compose.yml up --build
```

Then drive it: `sf-smartfabric live --url http://localhost:8770`.

## Turning on mTLS

The node speaks plain HTTP/JSON by default. For anything beyond a trusted network —
**especially the rented GPU boxes** — enable mutual TLS:

```
scripts/gen_certs.sh certs client-a          # demo PKI (use your real PKI in prod)
sf-smartfabric serve --tls-cert certs/server.crt --tls-key certs/server.key --tls-ca certs/ca.crt
```

The node then presents its cert and rejects any peer without one chaining to the
fabric CA. In Kubernetes/Helm, mount the certs from a Secret and flip `mtls.enabled`.

## Honest scope

- The Dockerfile, compose, k8s, and Helm chart are complete; they were **authored
  here but not built/applied in the sandbox** (no Docker/kubectl/helm daemon).
  Build the image once in your environment before relying on the tag.
- Every cloud/platform config references `ghcr.io/smarttasksorg/sf-smartfabric:latest` —
  a placeholder for your published image. Publish it first (`private/release/`).
- The base node is HTTP/JSON with no registry and no authn beyond the ConsentScope
  check. mTLS is available (above) and is the right baseline for any shared or
  internet-facing host; the registry and richer transports remain the follow-on
  fabric services in `docs/04`.
