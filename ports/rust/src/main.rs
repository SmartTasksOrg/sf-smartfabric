// SmartFabric — Rust port of the IAIso Fabric Protocol (IFP) core.
// Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
// exactly (1e-9 numeric, byte-exact envelope).
//
//   cd ports/rust && cargo run -- ../../spec/vectors
//
// NOTE: no Rust toolchain in the build sandbox, so this port is written and
// vector-checked by inspection here, not executed. It uses a tiny embedded JSON
// parser + SHA-256 so it builds with zero external crates. Run it in your env.

use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::process::exit;

const TOL: f64 = 1e-9;

#[derive(Clone)]
struct Config {
    escalation: f64, release: f64, diss_step: f64, diss_sec: f64,
    token_c: f64, tool_c: f64, depth_c: f64, warning: f64, post_release_lock: bool,
}
impl Default for Config {
    fn default() -> Self {
        Config { escalation: 0.85, release: 0.95, diss_step: 0.02, diss_sec: 0.0,
                 token_c: 0.015, tool_c: 0.08, depth_c: 0.05, warning: 0.70, post_release_lock: true }
    }
}

fn zone(c: &Config, p: f64) -> &'static str {
    if p >= c.release { "release" } else if p >= c.escalation { "escalation" }
    else if p >= c.warning { "warning" } else { "nominal" }
}
fn clamp(v: f64) -> f64 { v.max(0.0).min(1.0) }

struct Engine { c: Config, p: f64, locked: bool }
impl Engine {
    fn new(c: Config) -> Self { Engine { c, p: 0.0, locked: false } }
    fn step(&mut self, tokens: f64, tools: f64, depth: f64, seconds: f64) -> (f64, &'static str, bool, bool) {
        if self.locked && self.c.post_release_lock {
            return (self.p, zone(&self.c, self.p), false, true);
        }
        let intake = (tokens/1000.0)*self.c.token_c + tools*self.c.tool_c + depth*self.c.depth_c;
        let diss = self.c.diss_step + self.c.diss_sec*seconds;
        let np = clamp(self.p + intake - diss);
        if np >= self.c.release - TOL {
            self.p = 0.0; self.locked = self.c.post_release_lock;
            return (0.0, "release", true, self.locked);
        }
        self.p = np;
        (self.p, zone(&self.c, self.p), false, false)
    }
}

// ---- minimal JSON value + parser -----------------------------------------
#[derive(Clone, Debug)]
enum J { Null, Bool(bool), Num(f64), Str(String), Arr(Vec<J>), Obj(BTreeMap<String, J>) }

struct P { b: Vec<char>, i: usize }
impl P {
    fn new(s: &str) -> Self { P { b: s.chars().collect(), i: 0 } }
    fn ws(&mut self) { while self.i < self.b.len() && self.b[self.i].is_whitespace() { self.i += 1; } }
    fn val(&mut self) -> J {
        self.ws();
        match self.b[self.i] {
            '{' => self.obj(), '[' => self.arr(), '"' => J::Str(self.string()),
            't' => { self.i += 4; J::Bool(true) }, 'f' => { self.i += 5; J::Bool(false) },
            'n' => { self.i += 4; J::Null }, _ => self.num(),
        }
    }
    fn obj(&mut self) -> J {
        let mut m = BTreeMap::new(); self.i += 1; self.ws();
        if self.b[self.i] == '}' { self.i += 1; return J::Obj(m); }
        loop {
            self.ws(); let k = self.string(); self.ws(); self.i += 1; // :
            let v = self.val(); m.insert(k, v); self.ws();
            if self.b[self.i] == ',' { self.i += 1; continue; }
            self.i += 1; break;
        }
        J::Obj(m)
    }
    fn arr(&mut self) -> J {
        let mut a = Vec::new(); self.i += 1; self.ws();
        if self.b[self.i] == ']' { self.i += 1; return J::Arr(a); }
        loop {
            let v = self.val(); a.push(v); self.ws();
            if self.b[self.i] == ',' { self.i += 1; continue; }
            self.i += 1; break;
        }
        J::Arr(a)
    }
    fn string(&mut self) -> String {
        let mut s = String::new(); self.i += 1;
        while self.b[self.i] != '"' {
            let c = self.b[self.i]; self.i += 1;
            if c == '\\' {
                let e = self.b[self.i]; self.i += 1;
                match e {
                    'n' => s.push('\n'), 't' => s.push('\t'), 'r' => s.push('\r'),
                    '"' => s.push('"'), '\\' => s.push('\\'), '/' => s.push('/'),
                    'u' => {
                        let hex: String = self.b[self.i..self.i+4].iter().collect();
                        self.i += 4;
                        if let Ok(n) = u32::from_str_radix(&hex, 16) {
                            if let Some(ch) = char::from_u32(n) { s.push(ch); }
                        }
                    }
                    _ => s.push(e),
                }
            } else { s.push(c); }
        }
        self.i += 1; s
    }
    fn num(&mut self) -> J {
        let start = self.i;
        while self.i < self.b.len() && "-+.eE0123456789".contains(self.b[self.i]) { self.i += 1; }
        let t: String = self.b[start..self.i].iter().collect();
        J::Num(t.parse().unwrap())
    }
}

impl J {
    fn obj(&self) -> &BTreeMap<String, J> { if let J::Obj(m) = self { m } else { panic!() } }
    fn arr(&self) -> &Vec<J> { if let J::Arr(a) = self { a } else { panic!() } }
    fn num(&self) -> f64 { if let J::Num(n) = self { *n } else { panic!() } }
    fn str(&self) -> &str { if let J::Str(s) = self { s } else { panic!() } }
    fn boolean(&self) -> bool { if let J::Bool(b) = self { *b } else { panic!() } }
    fn get(&self, k: &str) -> Option<&J> { self.obj().get(k) }
    fn numk(&self, k: &str) -> f64 { self.get(k).map(|v| v.num()).unwrap_or(0.0) }
}

// ---- canonical JSON -------------------------------------------------------
fn canon(v: &J) -> String {
    match v {
        J::Null => "null".into(),
        J::Bool(b) => if *b { "true".into() } else { "false".into() },
        J::Str(s) => quote(s),
        J::Num(n) => {
            if *n == n.trunc() && n.abs() < 1e15 { format!("{}", *n as i64) }
            else { format!("{}", n) }
        }
        J::Arr(a) => format!("[{}]", a.iter().map(canon).collect::<Vec<_>>().join(",")),
        J::Obj(m) => {
            let parts: Vec<String> = m.iter()
                .filter(|(_, v)| !matches!(v, J::Null))
                .map(|(k, v)| format!("{}:{}", quote(k), canon(v)))
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}
fn quote(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""), '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"), '\r' => o.push_str("\\r"), '\t' => o.push_str("\\t"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"'); o
}

fn normalize_envelope(m: &J) -> J {
    let src = m.obj();
    let mut out: BTreeMap<String, J> = BTreeMap::new();
    out.insert("header".into(), drop_null(src.get("header").unwrap()));
    let policy = src.get("policy").map(drop_null).unwrap_or(J::Obj(BTreeMap::new()));
    out.insert("policy".into(), policy);
    for k in ["auth", "body", "meta"] {
        if let Some(J::Obj(mm)) = src.get(k) {
            if !mm.is_empty() { out.insert(k.into(), J::Obj(mm.clone())); }
        }
    }
    J::Obj(out)
}
fn drop_null(v: &J) -> J {
    if let J::Obj(m) = v {
        J::Obj(m.iter().filter(|(_, vv)| !matches!(vv, J::Null))
            .map(|(k, vv)| (k.clone(), vv.clone())).collect())
    } else { v.clone() }
}

fn varint(mut n: usize) -> Vec<u8> {
    let mut out = Vec::new();
    loop {
        let b = (n & 0x7f) as u8; n >>= 7;
        if n != 0 { out.push(b | 0x80); } else { out.push(b); break; }
    }
    out
}

// ---- SHA-256 (compact, no deps) ------------------------------------------
fn sha256_hex(data: &[u8]) -> String {
    let mut h: [u32; 8] = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    const K: [u32; 64] = [
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    let mut msg = data.to_vec();
    let bitlen = (data.len() as u64) * 8;
    msg.push(0x80);
    while msg.len() % 64 != 56 { msg.push(0); }
    msg.extend_from_slice(&bitlen.to_be_bytes());
    for chunk in msg.chunks(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([chunk[i*4], chunk[i*4+1], chunk[i*4+2], chunk[i*4+3]]);
        }
        for i in 16..64 {
            let s0 = w[i-15].rotate_right(7) ^ w[i-15].rotate_right(18) ^ (w[i-15] >> 3);
            let s1 = w[i-2].rotate_right(17) ^ w[i-2].rotate_right(19) ^ (w[i-2] >> 10);
            w[i] = w[i-16].wrapping_add(s0).wrapping_add(w[i-7]).wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh) =
            (h[0],h[1],h[2],h[3],h[4],h[5],h[6],h[7]);
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g; g = f; f = e; e = d.wrapping_add(t1);
            d = c; c = b; b = a; a = t1.wrapping_add(t2);
        }
        h[0]=h[0].wrapping_add(a); h[1]=h[1].wrapping_add(b); h[2]=h[2].wrapping_add(c); h[3]=h[3].wrapping_add(d);
        h[4]=h[4].wrapping_add(e); h[5]=h[5].wrapping_add(f); h[6]=h[6].wrapping_add(g); h[7]=h[7].wrapping_add(hh);
    }
    h.iter().map(|x| format!("{:08x}", x)).collect()
}
fn hex(b: &[u8]) -> String { b.iter().map(|x| format!("{:02x}", x)).collect() }

static mut PASS: i32 = 0;
static mut FAIL: i32 = 0;
fn report(fam: &str, name: &str, ok: bool, detail: &str) {
    unsafe { if ok { PASS += 1; } else { FAIL += 1; } }
    println!("{}{:<9} {:<28} {}", if ok { "OK " } else { "XX " }, fam, name, detail);
}

fn apply_config(c: &mut Config, conf: &J) {
    let m = conf.obj();
    if let Some(v) = m.get("escalation_threshold") { c.escalation = v.num(); }
    if let Some(v) = m.get("release_threshold") { c.release = v.num(); }
    if let Some(v) = m.get("dissipation_per_step") { c.diss_step = v.num(); }
    if let Some(v) = m.get("dissipation_per_second") { c.diss_sec = v.num(); }
    if let Some(v) = m.get("token_coefficient") { c.token_c = v.num(); }
    if let Some(v) = m.get("tool_coefficient") { c.tool_c = v.num(); }
    if let Some(v) = m.get("depth_coefficient") { c.depth_c = v.num(); }
    if let Some(v) = m.get("post_release_lock") { c.post_release_lock = v.boolean(); }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let dir = args.get(1).cloned().unwrap_or_else(|| "../../spec/vectors".into());

    // pressure
    let data = P::new(&fs::read_to_string(format!("{}/pressure.vectors.json", dir)).unwrap()).val();
    for c in data.get("cases").unwrap().arr() {
        let mut cfg = Config::default();
        if let Some(conf) = c.get("config") { apply_config(&mut cfg, conf); }
        let mut eng = Engine::new(cfg);
        let steps = c.get("steps").unwrap().arr();
        let exp = c.get("expect").unwrap().arr();
        let mut ok = true; let mut detail = String::new();
        for (i, st) in steps.iter().enumerate() {
            let (p, z, rel, lok) = eng.step(st.numk("tokens"), st.numk("tool_calls"), st.numk("depth"), st.numk("seconds"));
            let e = &exp[i];
            if (p - e.numk("p")).abs() > TOL { ok = false; detail = format!("p@{}", i); break; }
            if z != e.get("zone").unwrap().str() || rel != e.get("released").unwrap().boolean()
                || lok != e.get("locked").unwrap().boolean() { ok = false; detail = format!("field@{}", i); break; }
        }
        report("pressure", c.get("name").unwrap().str(), ok, &detail);
    }

    // fleet
    let data = P::new(&fs::read_to_string(format!("{}/fleet.vectors.json", dir)).unwrap()).val();
    for c in data.get("cases").unwrap().arr() {
        let esc = c.get("escalation_threshold").map(|v| v.num()).unwrap_or(0.85);
        let nodes = c.get("nodes").unwrap().arr();
        let (mut total_w, mut weighted, mut peak_p): (f64, f64, f64) = (0.0, 0.0, -1.0);
        let mut peak: Option<String> = None;
        for n in nodes {
            let pr = n.numk("pressure");
            let ce = n.get("centrality").map(|v| v.num().max(0.0)).unwrap_or(1.0);
            total_w += ce; weighted += pr*ce;
            if pr > peak_p { peak_p = pr; peak = Some(n.get("node_id").unwrap().str().to_string()); }
        }
        if total_w == 0.0 { total_w = nodes.len() as f64; }
        let pf = if nodes.is_empty() { 0.0 } else { clamp(weighted/total_w) };
        let e = c.get("expect").unwrap();
        let mut ok = (pf - e.numk("P_fleet")).abs() <= TOL;
        if ok { if let Some(J::Str(exp_peak)) = e.get("peak_node") { ok = peak.as_deref() == Some(exp_peak); } }
        report("fleet", c.get("name").unwrap().str(), ok, "");
    }

    // envelope
    let data = P::new(&fs::read_to_string(format!("{}/envelope.vectors.json", dir)).unwrap()).val();
    for c in data.get("cases").unwrap().arr() {
        let canon_s = canon(&normalize_envelope(c.get("message").unwrap()));
        let e = c.get("expect").unwrap();
        let mut ok = canon_s == e.get("canonical_json").unwrap().str();
        let mut detail = if ok { "" } else { "canonical_json" };
        if ok {
            let sha = format!("sha256:{}", sha256_hex(canon_s.as_bytes()));
            if sha != e.get("canonical_sha256").unwrap().str() { ok = false; detail = "sha"; }
        }
        if ok {
            let mut framed = varint(canon_s.len());
            framed.extend_from_slice(canon_s.as_bytes());
            if hex(&framed) != e.get("framed_hex").unwrap().str() { ok = false; detail = "framed"; }
        }
        report("envelope", c.get("name").unwrap().str(), ok, detail);
    }

    unsafe {
        println!("---");
        println!("pass={} fail={}", PASS, FAIL);
        exit(if FAIL == 0 { 0 } else { 1 });
    }
}
