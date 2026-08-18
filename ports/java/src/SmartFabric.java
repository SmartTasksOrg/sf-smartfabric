// SmartFabric — Java port of the IAIso Fabric Protocol (IFP) core.
// Independent reimplementation from spec/vectors (docs/07 + docs/08), not a
// transpile. Reproduces spec/vectors/*.json exactly (1e-9 numeric, byte-exact
// envelope). Single file, no external deps — run with the JDK's javac/java.
//
//   cd ports/java && javac src/SmartFabric.java -d out && \
//   java -cp out SmartFabric ../../spec/vectors

import java.io.IOException;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public class SmartFabric {

    static final double TOL = 1e-9;

    // ---- Pressure model ---------------------------------------------------
    static class Config {
        double escalation = 0.85, release = 0.95, dissStep = 0.02, dissSec = 0.0;
        double tokenCoeff = 0.015, toolCoeff = 0.08, depthCoeff = 0.05, warningBand = 0.70;
        boolean postReleaseLock = true;
    }

    static String zone(Config c, double p) {
        if (p >= c.release) return "release";
        if (p >= c.escalation) return "escalation";
        if (p >= c.warningBand) return "warning";
        return "nominal";
    }

    static class Engine {
        Config c; double p = 0.0; boolean locked = false;
        Engine(Config c) { this.c = c; }
        double clamp(double v) { return Math.max(0.0, Math.min(1.0, v)); }
        // returns [p, releasedFlag, lockedFlag] plus zone via helper
        Map<String,Object> step(double tokens, double tools, double depth, double seconds) {
            Map<String,Object> out = new LinkedHashMap<>();
            if (locked && c.postReleaseLock) {
                out.put("p", p); out.put("zone", zone(c, p));
                out.put("released", false); out.put("locked", true);
                return out;
            }
            double intake = (tokens/1000.0)*c.tokenCoeff + tools*c.toolCoeff + depth*c.depthCoeff;
            double diss = c.dissStep + c.dissSec*seconds;
            double np = clamp(p + intake - diss);
            if (np >= c.release - TOL) {
                p = 0.0; locked = c.postReleaseLock;
                out.put("p", 0.0); out.put("zone", "release");
                out.put("released", true); out.put("locked", locked);
                return out;
            }
            p = np;
            out.put("p", p); out.put("zone", zone(c, p));
            out.put("released", false); out.put("locked", false);
            return out;
        }
    }

    // ---- Fleet ------------------------------------------------------------
    static Map<String,Object> fleet(List<Map<String,Object>> nodes, double esc) {
        Map<String,Object> out = new LinkedHashMap<>();
        if (nodes.isEmpty()) {
            out.put("P_fleet", 0.0); out.put("peak_node", null);
            out.put("hot_nodes", new ArrayList<String>()); return out;
        }
        double totalW = 0, weighted = 0; double peakP = -1; String peak = null;
        List<String> hot = new ArrayList<>();
        for (Map<String,Object> n : nodes) {
            double pr = ((Number)n.get("pressure")).doubleValue();
            double ce = n.containsKey("centrality") ? ((Number)n.get("centrality")).doubleValue() : 1.0;
            ce = Math.max(ce, 0.0);
            totalW += ce; weighted += pr*ce;
            if (pr > peakP) { peakP = pr; peak = (String)n.get("node_id"); }
            if (pr >= esc - TOL) hot.add((String)n.get("node_id"));
        }
        if (totalW == 0) totalW = nodes.size();
        Collections.sort(hot);
        out.put("P_fleet", Math.max(0.0, Math.min(1.0, weighted/totalW)));
        out.put("peak_node", peak); out.put("hot_nodes", hot);
        return out;
    }

    // ---- Canonical JSON ---------------------------------------------------
    @SuppressWarnings("unchecked")
    static String canon(Object v) {
        if (v == null) return "null";
        if (v instanceof String) return quote((String)v);
        if (v instanceof Boolean) return ((Boolean)v) ? "true" : "false";
        if (v instanceof Number) {
            double d = ((Number)v).doubleValue();
            if (d == Math.rint(d) && !Double.isInfinite(d) && Math.abs(d) < 1e15
                    && !(v instanceof Double && ((String.valueOf(v)).contains(".") && !isIntValued(v)))) {
                long l = (long)d; return String.valueOf(l);
            }
            return trimNum(v.toString());
        }
        if (v instanceof Map) {
            TreeMap<String,Object> sorted = new TreeMap<>((Map<String,Object>)v);
            StringBuilder sb = new StringBuilder("{"); boolean first = true;
            for (Map.Entry<String,Object> e : sorted.entrySet()) {
                if (e.getValue() == null) continue;
                if (!first) sb.append(","); first = false;
                sb.append(quote(e.getKey())).append(":").append(canon(e.getValue()));
            }
            return sb.append("}").toString();
        }
        if (v instanceof List) {
            StringBuilder sb = new StringBuilder("["); boolean first = true;
            for (Object o : (List<Object>)v) {
                if (!first) sb.append(","); first = false;
                sb.append(canon(o));
            }
            return sb.append("]").toString();
        }
        throw new RuntimeException("uncanonicalizable: " + v.getClass());
    }
    static boolean isIntValued(Object v) {
        double d = ((Number)v).doubleValue(); return d == Math.rint(d);
    }
    static String trimNum(String s) { return s; }
    static String quote(String s) {
        StringBuilder sb = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int)c));
                    else sb.append(c);
            }
        }
        return sb.append("\"").toString();
    }

    @SuppressWarnings("unchecked")
    static Map<String,Object> normalizeEnvelope(Map<String,Object> m) {
        Map<String,Object> header = dropNull((Map<String,Object>)m.get("header"));
        Map<String,Object> policy = dropNull((Map<String,Object>)m.getOrDefault("policy", new LinkedHashMap<>()));
        Map<String,Object> out = new LinkedHashMap<>();
        out.put("header", header); out.put("policy", policy);
        if (m.get("auth") != null && !((Map<?,?>)m.get("auth")).isEmpty()) out.put("auth", m.get("auth"));
        if (m.get("body") != null && !((Map<?,?>)m.get("body")).isEmpty()) out.put("body", m.get("body"));
        if (m.get("meta") != null && !((Map<?,?>)m.get("meta")).isEmpty()) out.put("meta", m.get("meta"));
        return out;
    }
    @SuppressWarnings("unchecked")
    static Map<String,Object> dropNull(Map<String,Object> in) {
        Map<String,Object> out = new LinkedHashMap<>();
        for (Map.Entry<String,Object> e : in.entrySet())
            if (e.getValue() != null) out.put(e.getKey(), e.getValue());
        return out;
    }

    static String sha256hex(byte[] b) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] d = md.digest(b);
            StringBuilder sb = new StringBuilder();
            for (byte x : d) sb.append(String.format("%02x", x));
            return sb.toString();
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    static byte[] varint(int n) {
        List<Byte> out = new ArrayList<>();
        while (true) {
            int b = n & 0x7f; n >>>= 7;
            if (n != 0) out.add((byte)(b | 0x80));
            else { out.add((byte)b); break; }
        }
        byte[] r = new byte[out.size()];
        for (int i = 0; i < r.length; i++) r[i] = out.get(i);
        return r;
    }
    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) sb.append(String.format("%02x", x));
        return sb.toString();
    }

    // ---- Minimal JSON parser (for reading vector files) -------------------
    static class JP {
        final String s; int i = 0;
        JP(String s) { this.s = s; }
        Object parse() { skip(); Object v = val(); skip(); return v; }
        void skip() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }
        Object val() {
            char c = s.charAt(i);
            if (c == '{') return obj(); if (c == '[') return arr();
            if (c == '"') return str(); if (c == 't') { i+=4; return true; }
            if (c == 'f') { i+=5; return false; } if (c == 'n') { i+=4; return null; }
            return num();
        }
        Map<String,Object> obj() {
            Map<String,Object> m = new LinkedHashMap<>(); i++; skip();
            if (s.charAt(i) == '}') { i++; return m; }
            while (true) {
                skip(); String k = str(); skip(); i++; /* : */ skip();
                m.put(k, val()); skip();
                if (s.charAt(i) == ',') { i++; continue; }
                i++; break; /* } */
            }
            return m;
        }
        List<Object> arr() {
            List<Object> a = new ArrayList<>(); i++; skip();
            if (s.charAt(i) == ']') { i++; return a; }
            while (true) {
                skip(); a.add(val()); skip();
                if (s.charAt(i) == ',') { i++; continue; }
                i++; break;
            }
            return a;
        }
        String str() {
            StringBuilder sb = new StringBuilder(); i++; /* " */
            while (s.charAt(i) != '"') {
                char c = s.charAt(i++);
                if (c == '\\') {
                    char e = s.charAt(i++);
                    switch (e) {
                        case 'n': sb.append('\n'); break; case 't': sb.append('\t'); break;
                        case 'r': sb.append('\r'); break; case '"': sb.append('"'); break;
                        case '\\': sb.append('\\'); break; case '/': sb.append('/'); break;
                        case 'u': sb.append((char)Integer.parseInt(s.substring(i, i+4), 16)); i+=4; break;
                        default: sb.append(e);
                    }
                } else sb.append(c);
            }
            i++; return sb.toString();
        }
        Object num() {
            int start = i;
            while (i < s.length() && "-+.eE0123456789".indexOf(s.charAt(i)) >= 0) i++;
            String t = s.substring(start, i);
            if (t.contains(".") || t.contains("e") || t.contains("E")) return Double.parseDouble(t);
            return Long.parseLong(t);
        }
    }

    // ---- Vector runner ----------------------------------------------------
    static boolean approx(double a, double b) { return Math.abs(a-b) <= TOL; }
    static int pass = 0, fail = 0;

    @SuppressWarnings("unchecked")
    static void runPressure(Path dir) throws IOException {
        Map<String,Object> data = (Map<String,Object>) new JP(Files.readString(dir.resolve("pressure.vectors.json"))).parse();
        for (Object co : (List<Object>)data.get("cases")) {
            Map<String,Object> c = (Map<String,Object>)co;
            Config cfg = new Config();
            Map<String,Object> conf = (Map<String,Object>)c.getOrDefault("config", new LinkedHashMap<>());
            applyConfig(cfg, conf);
            Engine eng = new Engine(cfg);
            List<Object> steps = (List<Object>)c.get("steps");
            List<Object> exp = (List<Object>)c.get("expect");
            boolean ok = true; String detail = "";
            for (int k = 0; k < steps.size(); k++) {
                Map<String,Object> st = (Map<String,Object>)steps.get(k);
                Map<String,Object> got = eng.step(d(st,"tokens"), d(st,"tool_calls"), d(st,"depth"), d(st,"seconds"));
                Map<String,Object> e = (Map<String,Object>)exp.get(k);
                if (!approx((double)got.get("p"), ((Number)e.get("p")).doubleValue())) { ok=false; detail="p@"+k; break; }
                if (!got.get("zone").equals(e.get("zone"))) { ok=false; detail="zone@"+k; break; }
                if (!got.get("released").equals(e.get("released"))) { ok=false; detail="released@"+k; break; }
                if (!got.get("locked").equals(e.get("locked"))) { ok=false; detail="locked@"+k; break; }
            }
            report("pressure", (String)c.get("name"), ok, detail);
        }
    }
    static double d(Map<String,Object> m, String k) {
        return m.containsKey(k) ? ((Number)m.get(k)).doubleValue() : 0.0;
    }
    static void applyConfig(Config cfg, Map<String,Object> conf) {
        if (conf.containsKey("escalation_threshold")) cfg.escalation = ((Number)conf.get("escalation_threshold")).doubleValue();
        if (conf.containsKey("release_threshold")) cfg.release = ((Number)conf.get("release_threshold")).doubleValue();
        if (conf.containsKey("dissipation_per_step")) cfg.dissStep = ((Number)conf.get("dissipation_per_step")).doubleValue();
        if (conf.containsKey("dissipation_per_second")) cfg.dissSec = ((Number)conf.get("dissipation_per_second")).doubleValue();
        if (conf.containsKey("token_coefficient")) cfg.tokenCoeff = ((Number)conf.get("token_coefficient")).doubleValue();
        if (conf.containsKey("tool_coefficient")) cfg.toolCoeff = ((Number)conf.get("tool_coefficient")).doubleValue();
        if (conf.containsKey("depth_coefficient")) cfg.depthCoeff = ((Number)conf.get("depth_coefficient")).doubleValue();
        if (conf.containsKey("post_release_lock")) cfg.postReleaseLock = (Boolean)conf.get("post_release_lock");
    }

    @SuppressWarnings("unchecked")
    static void runFleet(Path dir) throws IOException {
        Map<String,Object> data = (Map<String,Object>) new JP(Files.readString(dir.resolve("fleet.vectors.json"))).parse();
        for (Object co : (List<Object>)data.get("cases")) {
            Map<String,Object> c = (Map<String,Object>)co;
            double esc = c.containsKey("escalation_threshold") ? ((Number)c.get("escalation_threshold")).doubleValue() : 0.85;
            Map<String,Object> r = fleet((List<Map<String,Object>>)(List<?>)c.get("nodes"), esc);
            Map<String,Object> e = (Map<String,Object>)c.get("expect");
            boolean ok = approx((double)r.get("P_fleet"), ((Number)e.get("P_fleet")).doubleValue());
            if (ok && r.get("peak_node") != null) ok = r.get("peak_node").equals(e.get("peak_node"));
            report("fleet", (String)c.get("name"), ok, ok ? "" : "mismatch");
        }
    }

    @SuppressWarnings("unchecked")
    static void runEnvelope(Path dir) throws IOException {
        Map<String,Object> data = (Map<String,Object>) new JP(Files.readString(dir.resolve("envelope.vectors.json"))).parse();
        for (Object co : (List<Object>)data.get("cases")) {
            Map<String,Object> c = (Map<String,Object>)co;
            Map<String,Object> msg = (Map<String,Object>)c.get("message");
            String canon = canon(normalizeEnvelope(msg));
            byte[] canonB = canon.getBytes(StandardCharsets.UTF_8);
            Map<String,Object> e = (Map<String,Object>)c.get("expect");
            boolean ok = canon.equals(e.get("canonical_json"));
            String detail = ok ? "" : "canonical_json";
            if (ok) {
                String sha = "sha256:" + sha256hex(canonB);
                if (!sha.equals(e.get("canonical_sha256"))) { ok=false; detail="sha"; }
            }
            if (ok) {
                byte[] framed = new byte[varint(canonB.length).length + canonB.length];
                byte[] vb = varint(canonB.length);
                System.arraycopy(vb, 0, framed, 0, vb.length);
                System.arraycopy(canonB, 0, framed, vb.length, canonB.length);
                if (!hex(framed).equals(e.get("framed_hex"))) { ok=false; detail="framed"; }
            }
            report("envelope", (String)c.get("name"), ok, detail);
        }
    }

    static void report(String fam, String name, boolean ok, String detail) {
        if (ok) pass++; else fail++;
        System.out.printf("%s%-9s %-28s %s%n", ok ? "OK " : "XX ", fam, name, detail);
    }

    public static void main(String[] args) throws IOException {
        Path dir = Path.of(args.length > 0 ? args[0] : "../../spec/vectors");
        runPressure(dir); runFleet(dir); runEnvelope(dir);
        System.out.println("---");
        System.out.printf("pass=%d fail=%d%n", pass, fail);
        System.exit(fail == 0 ? 0 : 1);
    }
}
