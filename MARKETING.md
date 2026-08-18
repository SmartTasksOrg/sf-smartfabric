# SmartFabric — positioning

**One line:** the governed layer for AI traffic — measure, monitor, audit, and
trace every LLM node in your architecture as one fleet.

**Who it's for:** SDK developers, platform integrators, security & compliance
auditors, and SREs who run many IAIso-governed AI agents/tools as one fleet.

**The wedge:** everyone else wraps a single agent. SmartFabric governs the
*fleet* — fleet pressure, cross-node escalation, real global halt, mandatory
provenance — because governance is a property of the whole system, and only a
common wire protocol can express it.

**Proof it's real on clone:** `pip install smartfabric && smartfabric --demo`
runs the pressure model to release, computes fleet pressure, and prints a
`FAB-*` conformance report — all offline.

**Honest boundary (a feature, not a caveat):** it bounds cooperating nodes and
makes them attestable; adversarial containment still needs a hardware/OS anchor,
and the conformance suite fails a node that claims caps it can't attest. Auditors
trust tools that tell them where the edge is.

**Stacks with:** SmartSeal (provenance), SmartRoute (trust routing), SmartLLMCost
(accounting). Bound to the open IAIso standard; bundles in SmartTasks.cloud.
