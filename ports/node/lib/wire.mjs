// SmartFabric — Node.js port of the IFP wire format.
// Independent implementation of the canonical-JSON rules in docs/08_WIRE_FORMAT.md.
// Must produce byte-identical output to the Python reference for every envelope
// vector — that byte-equality across two independent serializers is the interop
// proof that JSON.stringify + sort_keys alone doesn't give you for free.

// Canonical JSON: UTF-8, keys sorted by code point, no insignificant whitespace,
// omit absent optionals, integers bare, no floats in envelope fields.
export function canonicalJson(value) {
  return canon(value);
}

function canon(v) {
  if (v === null) return "null";
  const t = typeof v;
  if (t === "string") return JSON.stringify(v); // JSON string escaping
  if (t === "boolean") return v ? "true" : "false";
  if (t === "number") {
    if (!Number.isFinite(v)) throw new Error("non-finite number not allowed");
    // Integers render bare; the envelope carries no floats, but payloads may.
    // Match Python json.dumps: integers without ".0", floats via repr-ish.
    if (Number.isInteger(v)) return String(v);
    return jsonNumber(v);
  }
  if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
  if (t === "object") {
    const keys = Object.keys(v).filter((k) => v[k] !== undefined).sort();
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}";
  }
  throw new Error("uncanonicalizable value: " + t);
}

// Render a float the way Python's json does (shortest round-trip repr).
function jsonNumber(v) {
  // JS Number.prototype.toString already yields shortest round-trip form,
  // which matches Python's float repr for the values used in vectors.
  return String(v);
}

// Project a CIR message (already in canonical dict shape) to canonical bytes.
// We accept the same structural form the vectors store and re-emit it
// canonically, so ordering/whitespace/omission are enforced here, not upstream.
export function encodeEnvelope(message) {
  const norm = normalizeEnvelope(message);
  return Buffer.from(canonicalJson(norm), "utf-8");
}

function dropUndef(o) {
  const out = {};
  for (const [k, val] of Object.entries(o)) if (val !== undefined && val !== null) out[k] = val;
  return out;
}

function normalizeEnvelope(m) {
  const h = m.header || {};
  const header = dropUndef({
    id: h.id,
    verb: h.verb,
    verb_version: h.verb_version,
    from: h.from,
    to: h.to,
    idempotency: h.idempotency,
    trace: h.trace,
    deadline_ms: h.deadline_ms,
    qos_profile: h.qos_profile,
  });
  const p = m.policy || {};
  const policy = dropUndef({
    residency: p.residency,
    influence_class: p.influence_class,
    audit_required: p.audit_required,
  });
  const out = { header, policy };
  if (m.auth && Object.keys(m.auth).length) out.auth = m.auth;
  if (m.body && Object.keys(m.body).length) out.body = m.body;
  if (m.meta && Object.keys(m.meta).length) out.meta = m.meta;
  return out;
}

// --- LEB128 varint framing -------------------------------------------------

export function writeVarint(n) {
  if (n < 0) throw new Error("varint length must be non-negative");
  const out = [];
  for (;;) {
    let b = n & 0x7f;
    n = Math.floor(n / 128);
    if (n) out.push(b | 0x80);
    else { out.push(b); return Buffer.from(out); }
  }
}

export function readVarint(buf, offset = 0) {
  let result = 0, shift = 0, pos = offset;
  for (;;) {
    if (pos >= buf.length) throw new Error("truncated varint");
    const b = buf[pos++];
    result += (b & 0x7f) * Math.pow(2, shift);
    if (!(b & 0x80)) return [result, pos];
    shift += 7;
    if (shift > 63) throw new Error("varint too long");
  }
}

export function frame(payload) {
  return Buffer.concat([writeVarint(payload.length), payload]);
}

export function frameMessage(message) {
  return frame(encodeEnvelope(message));
}
