// SmartFabric / IFP meter for n8n (Function node).
//
// Drop this into an n8n Function node placed after any AI/LLM node. It reports
// the call to a running fabric node (smartfabric serve) and passes the pressure
// verdict downstream, so a workflow can branch/stop on escalation.
//
// Set via n8n environment variables SMARTFABRIC_NODE_URL / SMARTFABRIC_CONSENT_TOKEN.
// Thin adapter: containment logic lives in the fabric node, not here.

const NODE_URL = $env.SMARTFABRIC_NODE_URL || 'http://127.0.0.1:8770';
const CONSENT_TOKEN = $env.SMARTFABRIC_CONSENT_TOKEN || '';

const items = $input.all();
const out = [];

for (const item of items) {
  const tokens = item.json.tokens ?? item.json.total_tokens ?? 0;
  const toolCalls = item.json.tool_calls ?? 0;

  const envelope = {
    header: { id: '01N8N00000000000000000CALL', verb: 'invoke', verb_version: '0.1',
              from: 'iaiso://n8n@local/workflow', to: 'iaiso://node@local/demo' },
    policy: {},
    auth: CONSENT_TOKEN ? { token: CONSENT_TOKEN } : {},
    body: { schema_ref: 'invoke/1', payload: { tokens, tool_calls: toolCalls } },
  };

  const resp = await this.helpers.httpRequest({
    method: 'POST', url: `${NODE_URL}/cir`,
    body: JSON.stringify(envelope), headers: { 'Content-Type': 'application/json' },
  });
  const payload = (typeof resp === 'string' ? JSON.parse(resp) : resp).body?.payload || {};

  out.push({ json: { ...item.json, fabric: payload,
                     fabric_ok: !payload.error && !payload.escalation } });
}

return out;
