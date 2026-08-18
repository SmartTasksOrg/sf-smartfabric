# SmartFabric — manifesto

**You cannot govern what you cannot see, and you cannot see AI when every
integration is a different shape.**

Every team is wiring LLMs into systems that matter — pipelines, agents, CRMs,
CI. Each wire is bespoke. There is no shared layer where the AI's influence and
control can be measured, monitored, audited, and traced. That absence is the
risk. Not the model — the *ungoverned spread* of the model through your stack.

SmartFabric draws the line. It gives AI/LLM functionality its own hardened
layer, with one contract every node publishes and one protocol every node
speaks. Then the questions that were unanswerable become mechanical:

- *Is any node about to breach?* — pressure telemetry aggregates to `P_fleet`.
- *Can a global halt be honoured everywhere at once?* — Layer 6 is a fabric event.
- *Did an agent expand its reach without consent?* — default deny, invariant 4.
- *What did this node do, verifiably?* — provenance is mandatory, not optional.

We refuse three lies:

1. **The lie of the wrapper.** Wrapping one agent proves nothing about the fleet.
   Governance is a property of the *whole*, so it must live on the wire between nodes.
2. **The lie of self-report.** A model asked to police itself will optimise the
   police. Pressure is measured *outside* the model, at the infrastructure level.
3. **The lie of total containment.** In-process checks bound *cooperating* nodes.
   Adversarial nodes need an out-of-process anchor, and we say so, in the spec,
   in the schema, and in the conformance suite that fails a node claiming
   hardware caps it can't attest.

Safety through structure, not hope. Kin to the rest of the Smart* family, bound
to the IAIso core, honest about the boundary.
