#!/usr/bin/env node
// SmartFabric — Node vector runner.
// Loads the SAME spec/vectors/*.json the Python reference generated and checks
// that this independent implementation reproduces every expected output.
// Exit 0 iff all pass. This is the second-implementation interop proof.

import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PressureEngine, fleetPressure } from "../lib/pressure.mjs";
import { encodeEnvelope, frameMessage } from "../lib/wire.mjs";

const TOL = 1e-9;
const here = dirname(fileURLToPath(import.meta.url));
const VEC = join(here, "..", "..", "..", "spec", "vectors");

function load(name) {
  return JSON.parse(readFileSync(join(VEC, name), "utf-8"));
}
const approx = (a, b) => Math.abs(a - b) <= TOL;

function runPressure() {
  const out = [];
  for (const c of load("pressure.vectors.json").cases) {
    const eng = new PressureEngine(c.config || {});
    let ok = true, detail = "";
    for (let i = 0; i < c.steps.length; i++) {
      const o = eng.step(c.steps[i]);
      const e = c.expect[i];
      if (!approx(o.pressure, e.p)) { ok = false; detail = `step ${i}: p ${o.pressure} != ${e.p}`; break; }
      if (o.zone !== e.zone) { ok = false; detail = `step ${i}: zone ${o.zone} != ${e.zone}`; break; }
      if (o.released !== e.released) { ok = false; detail = `step ${i}: released`; break; }
      if (o.locked !== e.locked) { ok = false; detail = `step ${i}: locked`; break; }
    }
    out.push({ family: "pressure", name: c.name, ok, detail });
  }
  return out;
}

function runFleet() {
  const out = [];
  for (const c of load("fleet.vectors.json").cases) {
    const r = fleetPressure(c.nodes, c.escalation_threshold ?? 0.85);
    const e = c.expect;
    let ok = true, detail = "";
    if (!approx(r.value, e.P_fleet)) { ok = false; detail = `P_fleet ${r.value} != ${e.P_fleet}`; }
    else if (r.peak_node !== e.peak_node) { ok = false; detail = `peak ${r.peak_node} != ${e.peak_node}`; }
    else if (JSON.stringify([...r.hot_nodes].sort()) !== JSON.stringify([...e.hot_nodes].sort())) {
      ok = false; detail = `hot ${r.hot_nodes} != ${e.hot_nodes}`;
    }
    out.push({ family: "fleet", name: c.name, ok, detail });
  }
  return out;
}

function runEnvelope() {
  const out = [];
  for (const c of load("envelope.vectors.json").cases) {
    const canon = encodeEnvelope(c.message);
    const e = c.expect;
    let ok = true, detail = "";
    if (canon.toString("utf-8") !== e.canonical_json) { ok = false; detail = "canonical_json mismatch"; }
    else {
      const sha = "sha256:" + createHash("sha256").update(canon).digest("hex");
      if (sha !== e.canonical_sha256) { ok = false; detail = `sha ${sha}`; }
      else {
        const framed = frameMessage(c.message).toString("hex");
        if (framed !== e.framed_hex) { ok = false; detail = "framed_hex mismatch"; }
      }
    }
    out.push({ family: "envelope", name: c.name, ok, detail });
  }
  return out;
}

const results = [...runPressure(), ...runFleet(), ...runEnvelope()];
let fail = 0;
for (const r of results) {
  const mark = r.ok ? "OK " : "XX ";
  if (!r.ok) fail++;
  process.stdout.write(`${mark}${r.family.padEnd(9)} ${r.name.padEnd(28)} ${r.detail}\n`);
}
process.stdout.write(`---\npass=${results.length - fail} fail=${fail}\n`);
process.exit(fail === 0 ? 0 : 1);
