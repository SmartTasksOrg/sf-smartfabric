<?php
// SmartFabric — PHP port of the IAIso Fabric Protocol (IFP) core.
// Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
// exactly (1e-9 numeric, byte-exact envelope).
//
//   cd ports/php && php smartfabric.php ../../spec/vectors
//
// NOTE: no PHP toolchain in the build sandbox, so this port is written and
// vector-checked by inspection here, not executed. Run it in your environment.

const TOL = 1e-9;

function default_config(): array {
    return [
        'escalation' => 0.85, 'release' => 0.95, 'diss_step' => 0.02, 'diss_sec' => 0.0,
        'token_c' => 0.015, 'tool_c' => 0.08, 'depth_c' => 0.05, 'warning' => 0.70,
        'post_release_lock' => true,
    ];
}

function zone(array $c, float $p): string {
    if ($p >= $c['release']) return 'release';
    if ($p >= $c['escalation']) return 'escalation';
    if ($p >= $c['warning']) return 'warning';
    return 'nominal';
}

function clamp(float $v): float { return max(0.0, min(1.0, $v)); }

class Engine {
    public array $c; public float $p = 0.0; public bool $locked = false;
    public function __construct(array $c) { $this->c = $c; }
    public function step(float $tokens, float $tools, float $depth, float $seconds): array {
        if ($this->locked && $this->c['post_release_lock']) {
            return [$this->p, zone($this->c, $this->p), false, true];
        }
        $intake = ($tokens/1000.0)*$this->c['token_c'] + $tools*$this->c['tool_c'] + $depth*$this->c['depth_c'];
        $diss = $this->c['diss_step'] + $this->c['diss_sec']*$seconds;
        $np = clamp($this->p + $intake - $diss);
        if ($np >= $this->c['release'] - TOL) {
            $this->p = 0.0; $this->locked = $this->c['post_release_lock'];
            return [0.0, 'release', true, $this->locked];
        }
        $this->p = $np;
        return [$this->p, zone($this->c, $this->p), false, false];
    }
}

function fleet(array $nodes, float $esc): array {
    if (count($nodes) === 0) return [0.0, null, []];
    $totalW = 0.0; $weighted = 0.0; $peakP = -1.0; $peak = null; $hot = [];
    foreach ($nodes as $n) {
        $pr = (float)$n['pressure'];
        $ce = isset($n['centrality']) ? max((float)$n['centrality'], 0.0) : 1.0;
        $totalW += $ce; $weighted += $pr*$ce;
        if ($pr > $peakP) { $peakP = $pr; $peak = $n['node_id']; }
        if ($pr >= $esc - TOL) $hot[] = $n['node_id'];
    }
    if ($totalW == 0) $totalW = count($nodes);
    sort($hot);
    return [clamp($weighted/$totalW), $peak, $hot];
}

function canon($v): string {
    if ($v === null) return 'null';
    if (is_bool($v)) return $v ? 'true' : 'false';
    if (is_string($v)) return json_encode($v, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if (is_int($v)) return (string)$v;
    if (is_float($v)) {
        if ($v == floor($v) && abs($v) < 1e15) return (string)(int)$v;
        // Shortest round-trip form, like Python's repr and JavaScript's Number#toString
        // (sprintf('%.17g') printed 0.05 as 0.050000000000000003).
        $old = ini_set('serialize_precision', '-1');
        $s = json_encode($v);
        ini_set('serialize_precision', $old);
        return $s;
    }
    if (is_array($v)) {
        $isList = array_keys($v) === range(0, count($v) - 1);
        if ($isList) {
            return '[' . implode(',', array_map('canon', $v)) . ']';
        }
        $keys = array_keys($v);
        sort($keys);
        $parts = [];
        foreach ($keys as $k) {
            if ($v[$k] === null) continue;
            $parts[] = json_encode((string)$k, JSON_UNESCAPED_SLASHES) . ':' . canon($v[$k]);
        }
        return '{' . implode(',', $parts) . '}';
    }
    throw new Exception('uncanonicalizable');
}

function drop_null(array $in): array {
    return array_filter($in, fn($v) => $v !== null);
}

function normalize_envelope(array $m): array {
    $out = ['header' => drop_null($m['header'])];
    $out['policy'] = isset($m['policy']) ? drop_null($m['policy']) : [];
    foreach (['auth', 'body', 'meta'] as $k) {
        if (isset($m[$k]) && is_array($m[$k]) && count($m[$k]) > 0) $out[$k] = $m[$k];
    }
    return $out;
}

function varint(int $n): string {
    $out = '';
    while (true) {
        $b = $n & 0x7f; $n >>= 7;
        if ($n != 0) $out .= chr($b | 0x80);
        else { $out .= chr($b); break; }
    }
    return $out;
}

$pass = 0; $fail = 0;
function report(string $fam, string $name, bool $ok, string $detail = ''): void {
    global $pass, $fail;
    if ($ok) $pass++; else $fail++;
    printf("%s%-9s %-28s %s\n", $ok ? 'OK ' : 'XX ', $fam, $name, $detail);
}

function load(string $dir, string $name): array {
    return json_decode(file_get_contents("$dir/$name"), true);
}

$dir = $argv[1] ?? '../../spec/vectors';

// pressure
foreach (load($dir, 'pressure.vectors.json')['cases'] as $c) {
    $cfg = default_config();
    foreach (($c['config'] ?? []) as $k => $val) {
        $map = [
            'escalation_threshold' => 'escalation', 'release_threshold' => 'release',
            'dissipation_per_step' => 'diss_step', 'dissipation_per_second' => 'diss_sec',
            'token_coefficient' => 'token_c', 'tool_coefficient' => 'tool_c',
            'depth_coefficient' => 'depth_c', 'post_release_lock' => 'post_release_lock',
        ];
        if (isset($map[$k])) $cfg[$map[$k]] = $val;
    }
    $eng = new Engine($cfg);
    $ok = true; $detail = '';
    foreach ($c['steps'] as $i => $st) {
        [$p, $z, $rel, $lok] = $eng->step(
            (float)($st['tokens'] ?? 0), (float)($st['tool_calls'] ?? 0),
            (float)($st['depth'] ?? 0), (float)($st['seconds'] ?? 0)
        );
        $e = $c['expect'][$i];
        if (abs($p - $e['p']) > TOL) { $ok = false; $detail = "p@$i"; break; }
        if ($z !== $e['zone'] || $rel !== $e['released'] || $lok !== $e['locked']) {
            $ok = false; $detail = "field@$i"; break;
        }
    }
    report('pressure', $c['name'], $ok, $detail);
}

// fleet
foreach (load($dir, 'fleet.vectors.json')['cases'] as $c) {
    $esc = $c['escalation_threshold'] ?? 0.85;
    [$pf, $peak, $hot] = fleet($c['nodes'], $esc);
    $e = $c['expect'];
    $ok = abs($pf - $e['P_fleet']) <= TOL;
    if ($ok && $e['peak_node'] !== null) $ok = $peak === $e['peak_node'];
    report('fleet', $c['name'], $ok, '');
}

// envelope
foreach (load($dir, 'envelope.vectors.json')['cases'] as $c) {
    $canon = canon(normalize_envelope($c['message']));
    $e = $c['expect'];
    $ok = $canon === $e['canonical_json']; $detail = $ok ? '' : 'canonical_json';
    if ($ok) {
        $sha = 'sha256:' . hash('sha256', $canon);
        if ($sha !== $e['canonical_sha256']) { $ok = false; $detail = 'sha'; }
    }
    if ($ok) {
        $framed = varint(strlen($canon)) . $canon;
        if (bin2hex($framed) !== $e['framed_hex']) { $ok = false; $detail = 'framed'; }
    }
    report('envelope', $c['name'], $ok, $detail);
}

echo "---\n";
echo "pass=$pass fail=$fail\n";
exit($fail === 0 ? 0 : 1);
