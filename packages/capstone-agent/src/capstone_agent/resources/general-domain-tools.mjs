// Published Domain Pack tools. The host relay owns the worker address.
// A failed call stays a tool result so the task can continue.
export function createDomainTools(config, {fetchImpl = globalThis.fetch} = {}) {
  const domain = config.domainTools;
  if (!domain?.catalog?.tools) return [];
  return Object.entries(domain.catalog.tools).map(([name, schema]) => ({
    name,
    executionIdentity: 'owner',
    label: name,
    description: schema.description ?? name,
    parameters: schema.inputSchema,
    async execute(callId, args, signal) {
      signal?.throwIfAborted();
      const remaining = Math.min(180000, config.deadlineAt - Date.now());
      if (remaining <= 0) throw new Error('domain tool task deadline exceeded');
      const deadline = AbortSignal.timeout(Math.ceil(remaining));
      let response;
      try {
        response = await fetchImpl(domain.url, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + domain.grant},
          body: JSON.stringify({call_id: callId, name, arguments: args}),
          signal: signal ? AbortSignal.any([signal, deadline]) : deadline,
        });
      } catch (error) {
        signal?.throwIfAborted();
        throw new Error('domain tool call failed; continue the task without inventing a result');
      }
      let body = {};
      try { body = await response.json(); } catch { /* The relay returns JSON or the call failed. */ }
      if (!response.ok || typeof body.result_json !== 'string' || body.tool !== name || body.call_id !== callId) {
        throw new Error('domain tool call failed; continue the task without inventing a result');
      }
      return {
        content: [{type: 'text', text: body.result_json}],
        details: {tool: name, call_id: callId, ok: body.is_error !== true,
          ...(body.execution_receipt ? {execution_receipt: body.execution_receipt} : {})},
        isError: body.is_error === true,
      };
    },
  }));
}
