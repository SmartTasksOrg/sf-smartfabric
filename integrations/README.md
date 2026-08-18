# integrations/ — adapters for AI toolchains

Thin adapters that connect popular agent/LLM toolchains to a **running fabric
node** (`smartfabric serve`). They meter a call (tokens, tool invocations) and
report it to the node, which applies the IAIso pressure model and returns a
verdict — so containment becomes a *live guardrail* around an agent, not just an
after-the-fact audit.

These are deliberately thin. All the containment logic (consent-gating,
escalation, atomic release, halt) lives in the node — the adapter only meters and
relays. That keeps every integration consistent with the protocol by construction.

| Integration | File | What it does |
| --- | --- | --- |
| LangChain | `langchain/fabric_callback.py` | a callback that meters each LLM/tool call and can abort the chain on escalation/denial |
| n8n | `n8n/FabricMeter.function.js` | a Function-node snippet that meters a call and branches the workflow on the verdict |
| Flowise | `flowise/fabric-meter.js` | a Custom-Tool function that meters a call and throws on denial |
| GitHub Action | `github-action/action.yml` | runs static `FAB-*` + behavioral vectors on a fingerprint in CI |

## Prerequisite: a running node

All the runtime adapters (LangChain, n8n, Flowise) target a node service:

```
smartfabric serve --port 8770
```

Point the adapter at it with `SMARTFABRIC_NODE_URL` (and a `SMARTFABRIC_CONSENT_TOKEN`
if the node's fingerprint requires consent for expansion — the default one does).

## Honest status

- The GitHub Action runs entirely on the published package and is complete.
- The LangChain callback is runnable against a live node; it declares `langchain-core`
  as a peer dependency and stays importable without it.
- The n8n and Flowise snippets are written to their host's extension API (n8n
  Function node, Flowise custom tool). They're small and self-contained, but they
  run *inside* those products, so validate them in your n8n/Flowise instance —
  they aren't exercised by this repo's CI.

These meter against the current minimal node (HTTP/JSON). As the transport layer
grows (gRPC/mTLS, registry — docs/04), the adapters gain those transports without
changing what they measure.
