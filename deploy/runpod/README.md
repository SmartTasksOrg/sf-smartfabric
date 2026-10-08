# RunPod (GPU) deploy

RunPod runs a Docker image on a GPU host. Same node container as everywhere else.

- Import `template.json` (RunPod console → Templates → New, or the GraphQL API).
- Image: `ghcr.io/smarttasksorg/sf-smartfabric:0.5.0`; command: `serve --host 0.0.0.0 --port 8770`.
- Expose HTTP port 8770; RunPod gives you a proxy URL.

Verify: `sf-smartfabric live --url https://<pod-id>-8770.proxy.runpod.net`

Same caveat as vast.ai: a rented GPU box is shared/untrusted — enable mTLS and
restrict exposure before real traffic. Build/publish the image first (`private/release/`).
