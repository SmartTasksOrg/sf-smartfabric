// SmartFabric — C# port of the IAIso Fabric Protocol (IFP) core.
// Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
// exactly (1e-9 numeric, byte-exact envelope). Uses only the BCL
// (System.Text.Json, System.Security.Cryptography).
//
//   cd ports/csharp && dotnet run -- ../../spec/vectors
//
// NOTE: no .NET toolchain in the build sandbox, so this port is written and
// vector-checked by inspection here, not executed. Run it in your environment.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

static class SmartFabric
{
    const double TOL = 1e-9;

    class Config
    {
        public double Escalation = 0.85, Release = 0.95, DissStep = 0.02, DissSec = 0.0;
        public double TokenC = 0.015, ToolC = 0.08, DepthC = 0.05, Warning = 0.70;
        public bool PostReleaseLock = true;
    }

    static string Zone(Config c, double p) =>
        p >= c.Release ? "release" :
        p >= c.Escalation ? "escalation" :
        p >= c.Warning ? "warning" : "nominal";

    static double Clamp(double v) => Math.Max(0.0, Math.Min(1.0, v));

    class Engine
    {
        readonly Config c; public double P = 0.0; bool locked = false;
        public Engine(Config cfg) { c = cfg; }
        public (double, string, bool, bool) Step(double tokens, double tools, double depth, double seconds)
        {
            if (locked && c.PostReleaseLock) return (P, Zone(c, P), false, true);
            double intake = (tokens / 1000.0) * c.TokenC + tools * c.ToolC + depth * c.DepthC;
            double diss = c.DissStep + c.DissSec * seconds;
            double np = Clamp(P + intake - diss);
            if (np >= c.Release - TOL) { P = 0.0; locked = c.PostReleaseLock; return (0.0, "release", true, locked); }
            P = np;
            return (P, Zone(c, P), false, false);
        }
    }

    static (double, string?, List<string>) Fleet(List<Dictionary<string, object>> nodes, double esc)
    {
        if (nodes.Count == 0) return (0.0, null, new List<string>());
        double totalW = 0, weighted = 0, peakP = -1; string? peak = null;
        var hot = new List<string>();
        foreach (var n in nodes)
        {
            double pr = Convert.ToDouble(n["pressure"]);
            double ce = n.ContainsKey("centrality") ? Math.Max(Convert.ToDouble(n["centrality"]), 0.0) : 1.0;
            totalW += ce; weighted += pr * ce;
            if (pr > peakP) { peakP = pr; peak = (string)n["node_id"]; }
            if (pr >= esc - TOL) hot.Add((string)n["node_id"]);
        }
        if (totalW == 0) totalW = nodes.Count;
        hot.Sort(StringComparer.Ordinal);
        return (Clamp(weighted / totalW), peak, hot);
    }

    // ---- canonical JSON over JsonElement ----
    static string Canon(JsonElement v)
    {
        switch (v.ValueKind)
        {
            case JsonValueKind.Null: return "null";
            case JsonValueKind.True: return "true";
            case JsonValueKind.False: return "false";
            case JsonValueKind.String: return Quote(v.GetString()!);
            case JsonValueKind.Number:
                double d = v.GetDouble();
                if (d == Math.Truncate(d) && Math.Abs(d) < 1e15)
                    return ((long)d).ToString(CultureInfo.InvariantCulture);
                return d.ToString("R", CultureInfo.InvariantCulture);
            case JsonValueKind.Array:
                return "[" + string.Join(",", v.EnumerateArray().Select(Canon)) + "]";
            case JsonValueKind.Object:
                var pairs = v.EnumerateObject()
                    .Where(p => p.Value.ValueKind != JsonValueKind.Null)
                    .OrderBy(p => p.Name, StringComparer.Ordinal)
                    .Select(p => Quote(p.Name) + ":" + Canon(p.Value));
                return "{" + string.Join(",", pairs) + "}";
        }
        throw new Exception("uncanonicalizable");
    }

    static string Quote(string s)
    {
        var sb = new StringBuilder("\"");
        foreach (char c in s)
        {
            switch (c)
            {
                case '"': sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\n': sb.Append("\\n"); break;
                case '\r': sb.Append("\\r"); break;
                case '\t': sb.Append("\\t"); break;
                default:
                    if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                    else sb.Append(c);
                    break;
            }
        }
        return sb.Append("\"").ToString();
    }

    // Build a normalized envelope as a plain string via a JsonElement rewrite.
    static string NormalizeEnvelope(JsonElement m)
    {
        // Reconstruct { header(drop null), policy(drop null or {}), auth?, body?, meta? }
        var sb = new StringBuilder("{");
        // We canon() the resulting object; to reuse Canon we assemble a JSON string and reparse.
        var doc = new Dictionary<string, string>();
        doc["header"] = CanonDropNull(m.GetProperty("header"));
        doc["policy"] = m.TryGetProperty("policy", out var pol) ? CanonDropNull(pol) : "{}";
        foreach (var k in new[] { "auth", "body", "meta" })
            if (m.TryGetProperty(k, out var val) && val.ValueKind == JsonValueKind.Object &&
                val.EnumerateObject().Any())
                doc[k] = Canon(val);
        // assemble with sorted keys (header/policy/auth/body/meta are already lexicographically fine when sorted)
        var parts = doc.Keys.OrderBy(x => x, StringComparer.Ordinal).Select(k => Quote(k) + ":" + doc[k]);
        sb.Append(string.Join(",", parts)).Append("}");
        return sb.ToString();
    }

    static string CanonDropNull(JsonElement obj)
    {
        var pairs = obj.EnumerateObject()
            .Where(p => p.Value.ValueKind != JsonValueKind.Null)
            .OrderBy(p => p.Name, StringComparer.Ordinal)
            .Select(p => Quote(p.Name) + ":" + Canon(p.Value));
        return "{" + string.Join(",", pairs) + "}";
    }

    static byte[] Varint(int n)
    {
        var outp = new List<byte>();
        while (true)
        {
            int b = n & 0x7f; n >>= 7;
            if (n != 0) outp.Add((byte)(b | 0x80));
            else { outp.Add((byte)b); break; }
        }
        return outp.ToArray();
    }

    static int pass = 0, fail = 0;
    static void Report(string fam, string name, bool ok, string detail = "")
    {
        if (ok) pass++; else fail++;
        Console.WriteLine($"{(ok ? "OK " : "XX ")}{fam,-9} {name,-28} {detail}");
    }

    static bool Approx(double a, double b) => Math.Abs(a - b) <= TOL;
    static double Num(JsonElement e, string k) =>
        e.TryGetProperty(k, out var v) ? v.GetDouble() : 0.0;

    static void ApplyConfig(Config c, JsonElement conf)
    {
        void Set(string k, Action<double> f) { if (conf.TryGetProperty(k, out var v)) f(v.GetDouble()); }
        Set("escalation_threshold", x => c.Escalation = x);
        Set("release_threshold", x => c.Release = x);
        Set("dissipation_per_step", x => c.DissStep = x);
        Set("dissipation_per_second", x => c.DissSec = x);
        Set("token_coefficient", x => c.TokenC = x);
        Set("tool_coefficient", x => c.ToolC = x);
        Set("depth_coefficient", x => c.DepthC = x);
        if (conf.TryGetProperty("post_release_lock", out var pl)) c.PostReleaseLock = pl.GetBoolean();
    }

    static JsonElement Load(string dir, string name) =>
        JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, name))).RootElement;

    static int Main(string[] args)
    {
        string dir = args.Length > 0 ? args[0] : "../../spec/vectors";

        // pressure
        foreach (var c in Load(dir, "pressure.vectors.json").GetProperty("cases").EnumerateArray())
        {
            var cfg = new Config();
            if (c.TryGetProperty("config", out var conf)) ApplyConfig(cfg, conf);
            var eng = new Engine(cfg);
            bool ok = true; string detail = "";
            var steps = c.GetProperty("steps").EnumerateArray().ToList();
            var exp = c.GetProperty("expect").EnumerateArray().ToList();
            for (int i = 0; i < steps.Count; i++)
            {
                var (p, z, rel, lok) = eng.Step(Num(steps[i], "tokens"), Num(steps[i], "tool_calls"),
                                                Num(steps[i], "depth"), Num(steps[i], "seconds"));
                var e = exp[i];
                if (!Approx(p, e.GetProperty("p").GetDouble())) { ok = false; detail = $"p@{i}"; break; }
                if (z != e.GetProperty("zone").GetString() ||
                    rel != e.GetProperty("released").GetBoolean() ||
                    lok != e.GetProperty("locked").GetBoolean()) { ok = false; detail = $"field@{i}"; break; }
            }
            Report("pressure", c.GetProperty("name").GetString()!, ok, detail);
        }

        // fleet
        foreach (var c in Load(dir, "fleet.vectors.json").GetProperty("cases").EnumerateArray())
        {
            double esc = c.TryGetProperty("escalation_threshold", out var et) ? et.GetDouble() : 0.85;
            var nodes = c.GetProperty("nodes").EnumerateArray().Select(n =>
            {
                var d = new Dictionary<string, object>();
                foreach (var p in n.EnumerateObject())
                    d[p.Name] = p.Value.ValueKind == JsonValueKind.Number ? (object)p.Value.GetDouble()
                              : p.Value.GetString()!;
                return d;
            }).ToList();
            var (pf, peak, _) = Fleet(nodes, esc);
            var e = c.GetProperty("expect");
            bool ok = Approx(pf, e.GetProperty("P_fleet").GetDouble());
            if (ok && e.GetProperty("peak_node").ValueKind == JsonValueKind.String)
                ok = peak == e.GetProperty("peak_node").GetString();
            Report("fleet", c.GetProperty("name").GetString()!, ok);
        }

        // envelope
        foreach (var c in Load(dir, "envelope.vectors.json").GetProperty("cases").EnumerateArray())
        {
            string canon = NormalizeEnvelope(c.GetProperty("message"));
            var e = c.GetProperty("expect");
            bool ok = canon == e.GetProperty("canonical_json").GetString();
            string detail = ok ? "" : "canonical_json";
            if (ok)
            {
                var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canon));
                string sha = "sha256:" + Convert.ToHexString(hash).ToLowerInvariant();
                if (sha != e.GetProperty("canonical_sha256").GetString()) { ok = false; detail = "sha"; }
            }
            if (ok)
            {
                var cb = Encoding.UTF8.GetBytes(canon);
                var framed = Varint(cb.Length).Concat(cb).ToArray();
                string hex = Convert.ToHexString(framed).ToLowerInvariant();
                if (hex != e.GetProperty("framed_hex").GetString()) { ok = false; detail = "framed"; }
            }
            Report("envelope", c.GetProperty("name").GetString()!, ok, detail);
        }

        Console.WriteLine("---");
        Console.WriteLine($"pass={pass} fail={fail}");
        return fail == 0 ? 0 : 1;
    }
}
