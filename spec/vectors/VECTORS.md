# spec/vectors/ — the behavioral contract

These files are the **runnable definition of correct behaviour**. Static `FAB-*`
checks (docs/06) verify what a node *declares*; these vectors verify what an
implementation *computes*. An implementation is IFP-behavioral-conformant iff it
reproduces every `expect` here.

This mirrors how the IAIso core itself ships (`spec/*/vectors.json`) and how
QUIC / the Web Platform Tests establish interop: pin inputs → outputs, then make
every implementation match.

## Files

| File | Family | Compared |
|---|---|---|
| `pressure.vectors.json` | single-node `dp/dt` trajectory | `p` within 1e-9; `zone`/`released`/`locked` exact |
| `fleet.vectors.json` | `P_fleet` aggregation | `P_fleet` within 1e-9; `peak_node` + `hot_nodes` exact |
| `envelope.vectors.json` | canonical-JSON wire format | `canonical_json`, `canonical_sha256`, `framed_hex` **byte-exact** |

## Run them

```bash
smartfabric vectors                 # Python reference
node ports/node/bin/vectors.mjs     # independent Node port
ports/conformance/run.sh            # both, and require agreement
```

## Regenerate (only when intended behaviour changes)

```bash
python3 tools/gen_vectors.py
```

The Python reference is the source of truth. A vector diff on an unrelated change
is a **regression signal** — investigate before committing the new vectors.

## Why the envelope family matters most

The pressure/fleet vectors prove two implementations agree on *math*. The
envelope vectors prove two **independent serializers** — written separately,
sharing no code — emit the **same bytes** and the **same sha256** for the same
message, and frame them identically. That byte-level agreement is the difference
between "a protocol" and "an architecture with a JSON convention."
