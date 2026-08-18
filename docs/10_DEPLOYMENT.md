# 10 — Deployment

How to run the node (and registry) as real infrastructure. The deployable unit is
one container image; every target below consumes it. The configs live in
`deploy/`; this doc is the map.

## 10.1 One image, every platform

Build once, deploy anywhere:

```
docker build -f deploy/Dockerfile -t smartfabric-node .
```

The image runs `smartfabric serve`. The same image runs the registry
(`smartfabric registry`) — it's one package. Publish it (see
`private/release/` in the source repo) and point any target at the tag.

| Target | Files | Notes |
| --- | --- | --- |
| Docker | `deploy/Dockerfile` | single node on :8770 with a `/health` check |
| Compose | `deploy/docker-compose.yml` | two-node fabric + one-shot live conformance |
| Kubernetes | `deploy/k8s/deployment.yaml` | Deployment + Service, readiness/liveness probes |
| Helm | `deploy/helm/` | parameterised: replicas, image, **mTLS toggle** |
| GCP | `deploy/gcp/` | free-tier `e2-micro` (Terraform + cloud-init) |
| AWS | `deploy/aws/` | `t3.micro` EC2 (user-data) |
| Azure | `deploy/azure/` | `B1s` VM (cloud-init) |
| Fly.io | `deploy/fly/fly.toml` | image-based app with a TLS handler |
| Render | `deploy/render/render.yaml` | image-based web service |
| DigitalOcean | `deploy/digitalocean/` | App Platform spec + plain Droplet |
| vast.ai (GPU) | `deploy/vastai/` | GPU marketplace; image + on-start |
| RunPod (GPU) | `deploy/runpod/` | GPU pod template |

## 10.2 Quick start

```
# one node
docker run -p 8770:8770 smartfabric-node

# a two-node fabric + a live-conformance run
docker compose -f deploy/docker-compose.yml up --build

# verify any running node
smartfabric live --url http://localhost:8770
```

## 10.3 Kubernetes and Helm

`deploy/k8s/deployment.yaml` runs replicas behind a ClusterIP with `/health`
probes. The Helm chart parameterises replica count, image, and mTLS:

```
helm install fabric deploy/helm \
  --set image.repository=ghcr.io/youorg/smartfabric \
  --set replicaCount=3 \
  --set mtls.enabled=true \
  --set mtls.secretName=smartfabric-certs
```

With `mtls.enabled=true` the chart mounts `server.crt`/`server.key`/`ca.crt` from
the named Secret and starts the node with the TLS flags (docs/09 §9.2).

## 10.4 GPU providers (vast.ai, RunPod)

The node **governs** GPU-backed AI workers; it doesn't need the GPU itself. Running
it *next to* the model workers — same host or pod — puts the containment plane
where the compute is, so pressure, consent-gating, and halt enforcement sit next to
the thing being governed with no extra hop.

Both providers are image-based: give them
`ghcr.io/<org>/smartfabric:latest` and the command `serve --host 0.0.0.0 --port 8770`,
expose the port, and verify with `smartfabric live --url <provider-url>`.
`deploy/vastai/onstart.sh` also handles the case where you're adding the node as a
sidecar to a CUDA base image you already run (it installs the package from PyPI if
needed).

**These are rented, shared, untrusted hosts — turn on mTLS (docs/09 §9.2) and
restrict the exposed port before sending them anything real.**

## 10.5 Production posture (honest)

The base node is HTTP/JSON with no authentication beyond the ConsentScope check.
That is fine for a trusted internal network. For anything beyond that:

1. **Enable mTLS** — both node and registry (docs/09 §9.2). This is the baseline
   for any shared or internet-facing host.
2. **Restrict exposure** — the sample cloud configs open the port broadly for
   reachability; narrow the source range / put it behind a load balancer with real
   TLS termination.
3. **Run a registry** as the fleet's discovery + pressure-aggregation point
   (docs/09 §9.4), and treat it as control-plane infrastructure.
4. **Publish the image first** — every cloud/GPU config references a placeholder
   tag until you publish your own (that's what `private/release/` automates).

The registry today is single-process/in-memory (docs/09 §9.4); for HA you'll front
it with a persistent store. gRPC and the richer control-plane services remain the
follow-on described in docs/04. What ships now — node, mTLS, live conformance,
registry, one image, and this platform matrix — is enough to run a real governed
fleet.
