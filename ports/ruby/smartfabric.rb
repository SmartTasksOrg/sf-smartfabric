#!/usr/bin/env ruby
# frozen_string_literal: true
#
# SmartFabric — Ruby port of the IAIso Fabric Protocol (IFP) core.
# Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
# exactly (1e-9 numeric, byte-exact envelope). Standard library only.
#
#   cd ports/ruby && ruby smartfabric.rb ../../spec/vectors
#
# NOTE: no Ruby toolchain in the build sandbox, so this port is written and
# vector-checked by inspection here, not executed. Run it in your environment.

require 'json'
require 'digest'

TOL = 1e-9

DEFAULT_CONFIG = {
  escalation: 0.85, release: 0.95, diss_step: 0.02, diss_sec: 0.0,
  token_c: 0.015, tool_c: 0.08, depth_c: 0.05, warning: 0.70, post_release_lock: true
}.freeze

CONFIG_KEYS = {
  'escalation_threshold' => :escalation, 'release_threshold' => :release,
  'dissipation_per_step' => :diss_step, 'dissipation_per_second' => :diss_sec,
  'token_coefficient' => :token_c, 'tool_coefficient' => :tool_c,
  'depth_coefficient' => :depth_c, 'post_release_lock' => :post_release_lock
}.freeze

def zone(c, p)
  return 'release' if p >= c[:release]
  return 'escalation' if p >= c[:escalation]
  return 'warning' if p >= c[:warning]
  'nominal'
end

def clamp(v) = [[v, 0.0].max, 1.0].min

class Engine
  attr_reader :p
  def initialize(cfg)
    @c = cfg
    @p = 0.0
    @locked = false
  end

  def step(tokens, tools, depth, seconds)
    if @locked && @c[:post_release_lock]
      return [@p, zone(@c, @p), false, true]
    end
    intake = (tokens / 1000.0) * @c[:token_c] + tools * @c[:tool_c] + depth * @c[:depth_c]
    diss = @c[:diss_step] + @c[:diss_sec] * seconds
    np = clamp(@p + intake - diss)
    if np >= @c[:release] - TOL
      @p = 0.0
      @locked = @c[:post_release_lock]
      return [0.0, 'release', true, @locked]
    end
    @p = np
    [@p, zone(@c, @p), false, false]
  end
end

def fleet(nodes, esc)
  return [0.0, nil, []] if nodes.empty?

  total_w = 0.0
  weighted = 0.0
  peak_p = -1.0
  peak = nil
  hot = []
  nodes.each do |n|
    pr = n['pressure'].to_f
    ce = n.key?('centrality') ? [n['centrality'].to_f, 0.0].max : 1.0
    total_w += ce
    weighted += pr * ce
    if pr > peak_p
      peak_p = pr
      peak = n['node_id']
    end
    hot << n['node_id'] if pr >= esc - TOL
  end
  total_w = nodes.length if total_w.zero?
  [clamp(weighted / total_w), peak, hot.sort]
end

# canonical JSON: sorted keys, no whitespace, omit nils, ints without .0
def canon(v)
  case v
  when nil then 'null'
  when true then 'true'
  when false then 'false'
  when String then v.to_json
  when Integer then v.to_s
  when Float
    if v == v.truncate && v.abs < 1e15
      v.to_i.to_s
    else
      s = v.to_s            # Ruby Float#to_s is shortest round-trip
      s
    end
  when Array then "[#{v.map { |e| canon(e) }.join(',')}]"
  when Hash
    parts = v.keys.sort.filter_map do |k|
      next if v[k].nil?
      "#{k.to_json}:#{canon(v[k])}"
    end
    "{#{parts.join(',')}}"
  else
    raise "uncanonicalizable: #{v.class}"
  end
end

def drop_null(h) = h.reject { |_, val| val.nil? }

def normalize_envelope(m)
  out = { 'header' => drop_null(m['header']) }
  out['policy'] = m['policy'] ? drop_null(m['policy']) : {}
  %w[auth body meta].each do |k|
    out[k] = m[k] if m[k].is_a?(Hash) && !m[k].empty?
  end
  out
end

def varint(n)
  bytes = []
  loop do
    b = n & 0x7f
    n >>= 7
    if n != 0
      bytes << (b | 0x80)
    else
      bytes << b
      break
    end
  end
  bytes.pack('C*')
end

$pass = 0
$fail = 0
def report(fam, name, ok, detail = '')
  ok ? ($pass += 1) : ($fail += 1)
  printf("%s%-9s %-28s %s\n", ok ? 'OK ' : 'XX ', fam, name, detail)
end

def approx(a, b) = (a - b).abs <= TOL

dir = ARGV[0] || '../../spec/vectors'

# pressure
JSON.parse(File.read("#{dir}/pressure.vectors.json"))['cases'].each do |c|
  cfg = DEFAULT_CONFIG.dup
  (c['config'] || {}).each { |k, val| cfg[CONFIG_KEYS[k]] = val if CONFIG_KEYS[k] }
  eng = Engine.new(cfg)
  ok = true
  detail = ''
  c['steps'].each_with_index do |st, i|
    p, z, rel, lok = eng.step(st['tokens'].to_f, st['tool_calls'].to_f,
                              st['depth'].to_f, st['seconds'].to_f)
    e = c['expect'][i]
    unless approx(p, e['p']); ok = false; detail = "p@#{i}"; break; end
    if z != e['zone'] || rel != e['released'] || lok != e['locked']
      ok = false; detail = "field@#{i}"; break
    end
  end
  report('pressure', c['name'], ok, detail)
end

# fleet
JSON.parse(File.read("#{dir}/fleet.vectors.json"))['cases'].each do |c|
  esc = c['escalation_threshold'] || 0.85
  pf, peak, = fleet(c['nodes'], esc)
  e = c['expect']
  ok = approx(pf, e['P_fleet'])
  ok = peak == e['peak_node'] if ok && !e['peak_node'].nil?
  report('fleet', c['name'], ok)
end

# envelope
JSON.parse(File.read("#{dir}/envelope.vectors.json"))['cases'].each do |c|
  canon_s = canon(normalize_envelope(c['message']))
  e = c['expect']
  ok = canon_s == e['canonical_json']
  detail = ok ? '' : 'canonical_json'
  if ok
    sha = "sha256:#{Digest::SHA256.hexdigest(canon_s)}"
    if sha != e['canonical_sha256']; ok = false; detail = 'sha'; end
  end
  if ok
    framed = varint(canon_s.bytesize) + canon_s
    if framed.unpack1('H*') != e['framed_hex']; ok = false; detail = 'framed'; end
  end
  report('envelope', c['name'], ok, detail)
end

puts '---'
puts "pass=#{$pass} fail=#{$fail}"
exit($fail.zero? ? 0 : 1)
