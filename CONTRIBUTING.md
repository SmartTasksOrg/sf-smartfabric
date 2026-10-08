# Contributing to SmartFabric

SmartFabric is the reference implementation of the **IAIso Fabric Protocol (IFP)**.
The protocol is defined by `spec/vectors/*.json` and the docs in `docs/`, not by any
single codebase — so the bar for a change is simple: **it must keep every
implementation reproducing every vector, byte-for-byte.**

## The conformance bar

Before opening a PR, all of these must pass:

```
cd sf-smartfabric
pip install -e ".[dev]"
python -m pytest                 # unit + live + registry + mTLS tests
python -m sf_smartfabric vectors    # behavioural vectors (the protocol definition)
python -m sf_smartfabric live       # live FAB-L-* over the wire (spawns a node)
bash ports/conformance/run.sh    # cross-language interop (every present toolchain)
```

CI runs the same on Python + Node + Java + C++ + C. If your change alters observable
behaviour, it must be reflected in `spec/vectors/*.json` **and** reproduced by every
runnable port — otherwise it's a breaking protocol change and needs a version bump
and a docs update (see below).

## Changing the wire or the pressure model

These are protocol changes, not implementation details:

- Regenerate/extend the vectors with `tools/gen_vectors.py` and commit them.
- Update `docs/08_WIRE_FORMAT.md` (wire) or `docs/07_IAISO_CORE_BINDING.md` (pressure).
- Every port in `ports/` must be updated to match. The one portability gotcha is
  **shortest round-trip float formatting** in canonical JSON — get that right or the
  envelope won't be byte-identical across languages.
- Bump the version (see `CHANGELOG.md` for the scheme) and add a changelog entry.

## Adding a language port

1. Implement `step()` (pressure), `fleet()`, and canonical-JSON `encode()`.
2. Load `spec/vectors/*.json`, run each case, compare (1e-9 for numbers, exact bytes
   for the envelope).
3. Add it to `ports/conformance/run.sh` and the status table in `ports/README.md`.

The Java and C ports are the smallest complete examples to copy (single file, own
JSON parser + SHA-256). If a port reproduces the vectors, it's conformant — ship it.

## Adding a deployment target

Deployment configs live in `deploy/`. Every target runs the **same container image**
(`deploy/Dockerfile`) — don't fork the runtime per platform. Add the config, add a
row to the matrix in `deploy/README.md` and `docs/10_DEPLOYMENT.md`, and be explicit
about the security posture (plain HTTP vs mTLS, exposure).

## Style and honesty

- Keep the honest labelling: mark what's runnable-and-verified vs written-and-unrun,
  and don't claim a service exists before it does.
- Keep dependencies minimal — the reference and the ports use standard libraries only.
- Docs and code ship together: a feature isn't done until `docs/` describes it.

## Scope note

This repo is the public protocol + reference implementation. Internal release
machinery and any staged/unreleased namespaces live outside the public package and
are not part of contributions here.
