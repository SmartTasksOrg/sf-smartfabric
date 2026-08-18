# 03 — Two axes: IAIso containment layers (0–6) × physical substrate (S0–S10)

A node is described on **two orthogonal axes**. Keeping them separate removes the
biggest source of confusion when people hear "Layer 0" (it means different things in
each).

## Axis A — IAIso containment layers 0–6 (WHAT enforcement)
The core framework's control taxonomy (see `docs/07`). A node declares *which layers
it enforces*: `[0,1,2,4,5]`, etc. This is about **kinds of safety control**.

## Axis B — Physical substrate tiers S0–S10 (WHERE it sits)
Your original requirement — value "down to chips/circuits, hard drive, cpu/ram, cloud,
Chinese-firewalled, geo, topologically situated." This is about **placement**, and it
is what makes containment *physically real* (e.g. IAIso Layer 0 hardware caps only
mean something if the silicon/firmware substrate can enforce them).

| S | Substrate tier | Must expose | Why the fabric cares |
| --- | --- | --- | --- |
| **S0** | Silicon / circuits | ISA, accelerator, root-of-trust/attestation | anchors IAIso **Layer 0** — a FLOP cap is only trustworthy if the chip attests it |
| **S1** | Board / firmware | secure-boot state, firmware measurement | supply-chain integrity beneath the caps |
| **S2** | Storage | media class, at-rest crypto | where wiped-vs-persistent state lives (invariant 2) |
| **S3** | Compute (CPU/RAM/accel) | cores, RAM, confidential-compute | pressure `p` is FLOPs+Memory+Agency — measured here |
| **S4** | Node / OS | isolation (VM/container/enclave) | where infra-level pressure is computed (invariant 5: *outside* the model) |
| **S5** | Network | bandwidth, latency class | carries pressure telemetry + escalation events |
| **S6** | Cluster / orchestration | scheduler, mesh identity | issues node identity for ConsentScope (Layer 5) |
| **S7** | Cloud / region | provider, region, AZ | first residency boundary |
| **S8** | Jurisdiction / sovereignty | country, egress posture (incl. national firewalls), lawful-access | where consent + reset are legally valid; a node behind a national firewall declares `egress: restricted` so the fabric never routes governed flows across the boundary |
| **S9** | (reserved) | — | — |
| **S10** | Topology | degree, centrality, redundancy | feeds **fleet pressure** weighting + hotspot risk (Layer 3 / docs/05) |

## The mapping (why both axes are needed together)

| IAIso layer | Depends on substrate | Meaning |
| --- | --- | --- |
| Layer 0 (hardware caps) | S0, S1, S3 | a cap is only as real as the chip/firmware that attests it |
| Layer 3 (ecosystem coupling) | S5, S10 | fleet pressure needs the network + topology |
| Layer 4 (escalation) | S6, S8 | authorizers + where the authorization is legally valid |
| Layer 5 (ConsentScope) | S6, S8 | identity issuance + jurisdiction of consent |
| Layer 6 (existential/global halt) | S8, S10 | halt must reach every jurisdiction + every topological corner |

## Placement locator (in the node address)

```
iaiso://model-7@cn.bj/S3:gpu/S8:cn-restricted/S10:c0.82?layers=0,1,4,5
        └ identity ┘ └region┘ └compute┘ └jurisdiction┘ └centrality┘ └enforced IAIso layers┘
```
so a router can decide residency (S8), fleet-weight (S10), and whether the node
enforces the containment layers a flow requires — from the address alone, before
fetching the full fingerprint.
