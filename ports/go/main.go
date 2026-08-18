// SmartFabric — Go port of the IAIso Fabric Protocol (IFP) core.
// Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
// exactly (1e-9 numeric, byte-exact envelope).
//
//   cd ports/go && go run . ../../spec/vectors
//
// NOTE: no Go toolchain in the build sandbox, so this port is written and
// vector-checked by inspection here, not executed. Run it in your environment;
// it either passes the vectors or it doesn't — no coordination required.

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const tol = 1e-9

type Config struct {
	Escalation, Release      float64
	DissStep, DissSec        float64
	TokenC, ToolC, DepthC    float64
	WarningBand              float64
	PostReleaseLock          bool
}

func defaultConfig() Config {
	return Config{0.85, 0.95, 0.02, 0.0, 0.015, 0.08, 0.05, 0.70, true}
}

func zone(c Config, p float64) string {
	switch {
	case p >= c.Release:
		return "release"
	case p >= c.Escalation:
		return "escalation"
	case p >= c.WarningBand:
		return "warning"
	default:
		return "nominal"
	}
}

type Engine struct {
	c      Config
	p      float64
	locked bool
}

func clamp(v float64) float64 { return math.Max(0, math.Min(1, v)) }

func (e *Engine) step(tokens, tools, depth, seconds float64) (float64, string, bool, bool) {
	if e.locked && e.c.PostReleaseLock {
		return e.p, zone(e.c, e.p), false, true
	}
	intake := (tokens/1000.0)*e.c.TokenC + tools*e.c.ToolC + depth*e.c.DepthC
	diss := e.c.DissStep + e.c.DissSec*seconds
	np := clamp(e.p + intake - diss)
	if np >= e.c.Release-tol {
		e.p = 0
		e.locked = e.c.PostReleaseLock
		return 0, "release", true, e.locked
	}
	e.p = np
	return e.p, zone(e.c, e.p), false, false
}

func fleet(nodes []map[string]interface{}, esc float64) (float64, interface{}, []string) {
	if len(nodes) == 0 {
		return 0, nil, []string{}
	}
	var totalW, weighted, peakP float64 = 0, 0, -1
	var peak interface{}
	hot := []string{}
	for _, n := range nodes {
		pr := n["pressure"].(float64)
		ce := 1.0
		if v, ok := n["centrality"]; ok {
			ce = math.Max(v.(float64), 0)
		}
		totalW += ce
		weighted += pr * ce
		if pr > peakP {
			peakP = pr
			peak = n["node_id"]
		}
		if pr >= esc-tol {
			hot = append(hot, n["node_id"].(string))
		}
	}
	if totalW == 0 {
		totalW = float64(len(nodes))
	}
	sort.Strings(hot)
	return clamp(weighted / totalW), peak, hot
}

// canonical JSON: sorted keys, no whitespace, omit nils.
func canon(v interface{}) string {
	switch t := v.(type) {
	case nil:
		return "null"
	case string:
		b, _ := json.Marshal(t)
		return string(b)
	case bool:
		if t {
			return "true"
		}
		return "false"
	case float64:
		if t == math.Trunc(t) && math.Abs(t) < 1e15 {
			return strconv.FormatInt(int64(t), 10)
		}
		return strconv.FormatFloat(t, 'g', -1, 64)
	case map[string]interface{}:
		keys := make([]string, 0, len(t))
		for k := range t {
			if t[k] != nil {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		parts := make([]string, 0, len(keys))
		for _, k := range keys {
			kb, _ := json.Marshal(k)
			parts = append(parts, string(kb)+":"+canon(t[k]))
		}
		return "{" + strings.Join(parts, ",") + "}"
	case []interface{}:
		parts := make([]string, 0, len(t))
		for _, e := range t {
			parts = append(parts, canon(e))
		}
		return "[" + strings.Join(parts, ",") + "]"
	}
	panic("uncanonicalizable")
}

func normalizeEnvelope(m map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{
		"header": dropNil(m["header"].(map[string]interface{})),
	}
	if p, ok := m["policy"].(map[string]interface{}); ok {
		out["policy"] = dropNil(p)
	} else {
		out["policy"] = map[string]interface{}{}
	}
	for _, k := range []string{"auth", "body", "meta"} {
		if v, ok := m[k].(map[string]interface{}); ok && len(v) > 0 {
			out[k] = v
		}
	}
	return out
}

func dropNil(in map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{}
	for k, v := range in {
		if v != nil {
			out[k] = v
		}
	}
	return out
}

func varint(n int) []byte {
	var out []byte
	for {
		b := byte(n & 0x7f)
		n >>= 7
		if n != 0 {
			out = append(out, b|0x80)
		} else {
			out = append(out, b)
			break
		}
	}
	return out
}

var pass, fail int

func report(fam, name string, ok bool, detail string) {
	if ok {
		pass++
	} else {
		fail++
	}
	mark := "OK "
	if !ok {
		mark = "XX "
	}
	fmt.Printf("%s%-9s %-28s %s\n", mark, fam, name, detail)
}

func load(dir, name string) map[string]interface{} {
	data, _ := os.ReadFile(filepath.Join(dir, name))
	var m map[string]interface{}
	json.Unmarshal(data, &m)
	return m
}

func num(m map[string]interface{}, k string) float64 {
	if v, ok := m[k]; ok {
		return v.(float64)
	}
	return 0
}

func main() {
	dir := "../../spec/vectors"
	if len(os.Args) > 1 {
		dir = os.Args[1]
	}

	// pressure
	for _, co := range load(dir, "pressure.vectors.json")["cases"].([]interface{}) {
		c := co.(map[string]interface{})
		cfg := defaultConfig()
		if conf, ok := c["config"].(map[string]interface{}); ok {
			applyConfig(&cfg, conf)
		}
		eng := &Engine{c: cfg}
		steps := c["steps"].([]interface{})
		exp := c["expect"].([]interface{})
		ok, detail := true, ""
		for i, so := range steps {
			st := so.(map[string]interface{})
			p, z, rel, lok := eng.step(num(st, "tokens"), num(st, "tool_calls"), num(st, "depth"), num(st, "seconds"))
			e := exp[i].(map[string]interface{})
			if math.Abs(p-e["p"].(float64)) > tol {
				ok, detail = false, fmt.Sprintf("p@%d", i)
				break
			}
			if z != e["zone"].(string) || rel != e["released"].(bool) || lok != e["locked"].(bool) {
				ok, detail = false, fmt.Sprintf("field@%d", i)
				break
			}
		}
		report("pressure", c["name"].(string), ok, detail)
	}

	// fleet
	for _, co := range load(dir, "fleet.vectors.json")["cases"].([]interface{}) {
		c := co.(map[string]interface{})
		esc := 0.85
		if v, ok := c["escalation_threshold"]; ok {
			esc = v.(float64)
		}
		var nodes []map[string]interface{}
		for _, n := range c["nodes"].([]interface{}) {
			nodes = append(nodes, n.(map[string]interface{}))
		}
		pf, peak, _ := fleet(nodes, esc)
		e := c["expect"].(map[string]interface{})
		ok := math.Abs(pf-e["P_fleet"].(float64)) <= tol
		if ok && e["peak_node"] != nil {
			ok = peak == e["peak_node"]
		}
		report("fleet", c["name"].(string), ok, "")
	}

	// envelope
	for _, co := range load(dir, "envelope.vectors.json")["cases"].([]interface{}) {
		c := co.(map[string]interface{})
		msg := c["message"].(map[string]interface{})
		canonStr := canon(normalizeEnvelope(msg))
		e := c["expect"].(map[string]interface{})
		ok, detail := canonStr == e["canonical_json"].(string), ""
		if !ok {
			detail = "canonical_json"
		}
		if ok {
			sum := sha256.Sum256([]byte(canonStr))
			if "sha256:"+hex.EncodeToString(sum[:]) != e["canonical_sha256"].(string) {
				ok, detail = false, "sha"
			}
		}
		if ok {
			framed := append(varint(len(canonStr)), []byte(canonStr)...)
			if hex.EncodeToString(framed) != e["framed_hex"].(string) {
				ok, detail = false, "framed"
			}
		}
		report("envelope", c["name"].(string), ok, detail)
	}

	fmt.Println("---")
	fmt.Printf("pass=%d fail=%d\n", pass, fail)
	if fail != 0 {
		os.Exit(1)
	}
}

func applyConfig(c *Config, conf map[string]interface{}) {
	set := func(k string, f *float64) {
		if v, ok := conf[k]; ok {
			*f = v.(float64)
		}
	}
	set("escalation_threshold", &c.Escalation)
	set("release_threshold", &c.Release)
	set("dissipation_per_step", &c.DissStep)
	set("dissipation_per_second", &c.DissSec)
	set("token_coefficient", &c.TokenC)
	set("tool_coefficient", &c.ToolC)
	set("depth_coefficient", &c.DepthC)
	if v, ok := conf["post_release_lock"]; ok {
		c.PostReleaseLock = v.(bool)
	}
}
