# demo/

There is nothing to configure. The demo ships its synthetic data inside the
package (`schema/example.fingerprint.json`, `examples/fleet.example.json`) so it
works the second you clone:

```bash
smartfabric --demo
```

It runs three stages offline — single-node pressure to atomic release, fleet
pressure aggregation, and the FAB-* conformance suite — and exits non-zero if the
example fingerprint fails any MUST check.
