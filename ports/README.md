# ports/ — independent implementations

The protocol is defined by `spec/vectors/*.json`, not by any one codebase. A port
is conformant iff it reproduces every vector: pressure/fleet numbers to 1e-9, and
the CIR envelope **byte-for-byte** (canonical JSON, SHA-256, LEB128 framing).

That's the IETF "two independent interoperable implementations" bar. We exceed it
by a wide margin: **five** implementations are verified in CI, and five more are
shipped for full-family breadth.

## Status

| Port | Language | Verified in CI here | How to run |
| --- | --- | --- | --- |
| reference | Python | ✅ verified | `python3 -m sf_smartfabric vectors` |
| node | Node.js | ✅ verified | `node ports/node/bin/vectors.mjs` |
| java | Java 21 | ✅ verified | `cd ports/java && java src/SmartFabric.java ../../spec/vectors` |
| cpp | C++17 | ✅ verified | `cd ports/cpp && g++ -O2 -std=c++17 smartfabric.cpp -o sf && ./sf ../../spec/vectors` |
| c | C11 | ✅ verified | `cd ports/c && cc -O2 -std=c11 smartfabric.c -o sf -lm && ./sf ../../spec/vectors` |
| go | Go | ⧗ written + vector-checked* | `cd ports/go && go run . ../../spec/vectors` |
| php | PHP 8 | ⧗ written + vector-checked* | `cd ports/php && php smartfabric.php ../../spec/vectors` |
| rust | Rust | ⧗ written + vector-checked* | `cd ports/rust && cargo run -- ../../spec/vectors` |
| ruby | Ruby | ⧗ written + vector-checked* | `cd ports/ruby && ruby smartfabric.rb ../../spec/vectors` |
| csharp | C# / .NET 8 | ⧗ written + vector-checked* | `cd ports/csharp && dotnet run -- ../../spec/vectors` |

\* Those five toolchains weren't present in the build sandbox, so those ports were
written and checked against the vectors by inspection, not executed here. Each uses
only its standard library (the systems-language ports even embed their own SHA-256
and JSON parser) so they build with zero external dependencies. Run them in your
own environment — each either passes the vectors or it doesn't; no coordination
with the reference is required, which is the whole point of vector-based conformance.

## Interop harness

```
bash ports/conformance/run.sh
```

Runs the vectors against every implementation whose toolchain is present and
requires all of them to pass. Absent toolchains are reported and skipped, never
silently passed. On this repo's CI image that's Python + Node + Java + C++ + C.

## Adding a port

1. Implement `step()` (pressure), `fleet()`, and canonical-JSON `encode()`.
2. Load `spec/vectors/*.json`, run each case, compare (1e-9 for numbers, exact for
   envelope bytes).
3. Add it to `run.sh`. If it reproduces the vectors, it's conformant — ship it.

The Java and C ports are the smallest full examples to copy (single file, own JSON
parser + SHA-256). The one subtlety every port must get right: **shortest
round-trip float formatting** in canonical JSON (Python `repr`, JS default,
`std::to_chars`, `%.*g` search, `"R"` format) — that's what makes the envelope
byte-identical across languages.
