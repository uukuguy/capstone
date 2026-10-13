import test from "node:test";
import assert from "node:assert/strict";
import { configureReplyPhase } from "../src/reply-phase.mjs";

test("reply phase is explicit, waits for the current turn, removes tools and restores only its original scope", async () => {
  const handlers = new Map(), tools = new Map();
  let active = ['domain_run', 'domain_query', 'capstone_begin_reply'];
  let state = { schema: 'capstone-reply-phase/1', attempt_id: 'attempt_one', phase: 'research' };
  configureReplyPhase({ on: (name, handler) => handlers.set(name, handler),
    registerTool: tool => tools.set(tool.name, tool), getActiveTools: () => active,
    setActiveTools: names => { active = [...names]; } },
    { attemptId: 'attempt_one', read: () => state, write: next => { state = next; } });
  handlers.get('agent_start')({});
  const result = await tools.get('capstone_begin_reply').execute('finish', { outcome: 'partial' });
  assert.equal(result.details.ok, true);
  assert.equal(state.phase, 'research');
  assert.equal(active.length, 3);
  handlers.get('turn_end')({});
  assert.equal(state.phase, 'reply');
  assert.deepEqual(active, []);
  const user = { role: 'user', content: 'Original task' };
  const reply = handlers.get('context')({ messages: [user] });
  assert.equal(reply.messages[0], user);
  assert.match(reply.messages.at(-1).content, /Write the formal reply now/);
  assert.match(reply.messages.at(-1).content, /partial/);
  assert.equal(handlers.get('context')({ messages: reply.messages }).messages.length, 2);
  handlers.get('before_model_request')({ context: { tools: [] } });
  state = { ...state, phase: 'research' }; // Host recovery after a failed check.
  handlers.get('agent_start')({});
  assert.deepEqual(active, ['domain_run', 'domain_query', 'capstone_begin_reply']);
  assert.deepEqual(handlers.get('context')({ messages: reply.messages }).messages, [user]);
  assert.deepEqual(result.details.evidence_refs, []);
});

test("invalid phase requests cannot complete research or create evidence", async () => {
  const tools = new Map();
  configureReplyPhase({ on: () => {}, registerTool: tool => tools.set(tool.name, tool),
    getActiveTools: () => [], setActiveTools: () => {} },
    { attemptId: 'attempt_one', read: () => ({ schema: 'capstone-reply-phase/1', attempt_id: 'attempt_one', phase: 'research' }), write: () => {} });
  const result = await tools.get('capstone_begin_reply').execute('invalid', { outcome: 'completed', endpoint: '/secret' });
  assert.equal(result.isError, true);
  assert.deepEqual(result.details.result_refs, []);
});
