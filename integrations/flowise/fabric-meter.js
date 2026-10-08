// SmartFabric / IFP meter for Flowise (Custom Tool / Custom Function).
//
// Reports a metered call to a running fabric node (sf-smartfabric serve) and returns
// the pressure verdict, so a Flowise agent can be gated by IAIso containment.

const NODE_URL = process.env.SMARTFABRIC_NODE_URL || 'http://127.0.0.1:8770';
const CONSENT_TOKEN = process.env.SMARTFABRIC_CONSENT_TOKEN || '';

async function meter({ tokens = 0, tool_calls = 0 }) {
  const envelope = {
    header: { id: '01FLW0000000000000000CALL', verb: 'invoke', verb_version: '0.1',
              from: 'iaiso://flowise@local/agent', to: 'iaiso://node@local/demo' },
    policy: {},
    auth: CONSENT_TOKEN ? { token: CONSENT_TOKEN } : {},
    body: { schema_ref: 'invoke/1', payload: { tokens, tool_calls } },
  };
  const res = await fetch(`${NODE_URL}/cir`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(envelope),
  });
  const data = await res.json();
  const payload = data.body?.payload || {};
  if (payload.error) throw new Error(`fabric denied: ${JSON.stringify(payload.error)}`);
  return payload; // { accepted, p, zone, released, escalation? }
}

module.exports = { meter };
