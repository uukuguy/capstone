import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { createAgentSession, DefaultResourceLoader, SettingsManager, SessionManager,
  createWriteTool, createCodingTools } from '@earendil-works/pi-coding-agent';
import { createAssistantMessageEventStream } from '@earendil-works/pi-ai';
import * as host from '../../capstone-agent/src/capstone_agent/resources/general-sdk.mjs';

const model = { id: 'offline-bridge', name: 'Offline bridge', provider: 'offline',
  api: 'openai-completions', baseUrl: 'http://127.0.0.1:1', reasoning: false,
  input: ['text'], contextWindow: 32000, maxTokens: 1024,
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } };
const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');

// Only model output is scripted. Session, extension runner, tool execution and
// persistence use the pinned real SDK. No Provider or host authentication is used.
async function fixture(t, { tools = [], extensions = [], manager, root } = {}) {
  root ??= await mkdtemp(join(tmpdir(), 'capstone-enterprise-bridge-'));
  if (!manager) t.after(() => rm(root, { recursive: true, force: true }));
  const outputs = [];
  const runtime = {
    getModel: () => model, hasConfiguredAuth: () => true,
    getAuth: async () => ({ auth: { apiKey: 'offline-fixture' } }),
    isUsingOAuth: () => false,
    streamSimple: () => {
      const stream = createAssistantMessageEventStream();
      const content = outputs.shift() ?? [{ type: 'text', text: 'Offline completion' }];
      const message = { role: 'assistant', content, api: model.api, provider: model.provider,
        model: model.id, timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: content.some(c => c.type === 'toolCall') ? 'toolUse' : 'stop' };
      stream.push({ type: 'done', reason: message.stopReason, message });
      stream.end();
      return stream;
    },
  };
  const settingsManager = SettingsManager.inMemory({ retry: { enabled: false },
    compaction: { enabled: false } });
  const loader = new DefaultResourceLoader({ cwd: root, agentDir: root,
    settingsManager, noExtensions: true, noSkills: true, noPromptTemplates: true,
    noThemes: true, noContextFiles: true, extensionFactories: extensions });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  const activeTools = [...tools.map(tool => tool.name),
    ...loader.getExtensions().extensions.flatMap(extension => [...extension.tools.keys()])];
  const { session } = await createAgentSession({ cwd: root, agentDir: root,
    modelRuntime: runtime, model, thinkingLevel: 'off', resourceLoader: loader,
    settingsManager, tools: activeTools, customTools: tools,
    sessionManager: manager ?? SessionManager.create(root, root) });
  t.after(() => session.dispose());
  await session.bindExtensions({ onError: error => { throw error; } });
  session.setActiveToolsByName(activeTools);
  return { root, session, outputs };
}

function guarded(tool, admit) {
  return host.guardToolExecution(tool, admit);
}

test('host guard checks final extension-mutated arguments before a real native write', async t => {
  const root = await mkdtemp(join(tmpdir(), 'capstone-guard-write-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const proposed = { path: 'allowed.txt', content: 'fixture' };
  let checked;
  const tool = guarded(createWriteTool(root), async call => {
    checked = call;
    return { accepted: call.args.path === 'allowed.txt', reason: 'Path outside this action grant' };
  });
  const { session, outputs } = await fixture(t, { root, tools: [tool],
    extensions: [pi => pi.on('tool_call', event => { event.input.path = 'denied.txt'; })] });
  outputs.push([{ type: 'toolCall', id: 'write-1', name: 'write', arguments: proposed }]);
  await session.prompt('Write the supplied fixture', { expandPromptTemplates: false });
  await assert.rejects(readFile(join(root, 'denied.txt')), { code: 'ENOENT' });
  assert.equal(checked.toolName, 'write');
  assert.equal(checked.toolCallId, 'write-1');
  assert.notEqual(digest(checked.args), digest(proposed));
  assert.equal(session.messages.find(m => m.role === 'toolResult').isError, true);
  assert.match(JSON.stringify(session.messages.find(m => m.role === 'toolResult').content),
    /Path outside this action grant/);
  assert.equal(session.messages.at(-1).role, 'assistant');
});

test('admitted native action persists and reopened session accepts another message', async t => {
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-reopen-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const tool = guarded(createWriteTool(root), async () => ({ accepted: true }));
  const first = await fixture(t, { root, tools: [tool] });
  first.outputs.push([{ type: 'toolCall', id: 'write-2', name: 'write',
    arguments: { path: 'result.txt', content: 'saved result' } }]);
  await first.session.prompt('Create a result', { expandPromptTemplates: false });
  assert.equal(first.session.messages.find(m => m.role === 'toolResult')?.isError, false,
    JSON.stringify(first.session.messages.find(m => m.role === 'toolResult')));
  const file = first.session.sessionManager.getSessionFile();
  first.session.dispose();
  const second = await fixture(t, { root, tools: [tool], manager: SessionManager.open(file) });
  assert.equal(second.session.messages.filter(m => m.role === 'toolResult').length, 1);
  await second.session.prompt('Continue the same task', { expandPromptTemplates: false });
  assert.equal(second.session.messages.filter(m => m.role === 'user').length, 2);
  assert.equal(await readFile(join(root, 'result.txt'), 'utf8'), 'saved result');
});

test('extension block prevents admission and execution without stopping the session', async t => {
  let admissions = 0;
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-block-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const { session, outputs } = await fixture(t, { root,
    tools: [guarded(createWriteTool(root), async () => { admissions++; return { accepted: true }; })],
    extensions: [pi => pi.on('tool_call', () => ({ block: true, reason: 'Unavailable action' }))] });
  outputs.push([{ type: 'toolCall', id: 'blocked', name: 'write',
    arguments: { path: 'blocked.txt', content: 'never written' } }]);
  await session.prompt('Try the action');
  assert.equal(admissions, 0);
  await assert.rejects(readFile(join(root, 'blocked.txt')), { code: 'ENOENT' });
  assert.equal(session.messages.at(-1).stopReason, 'stop');
});

test('arguments retained by an extension cannot change the admitted execution', async t => {
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-snapshot-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  let retained;
  const { session, outputs } = await fixture(t, { root,
    extensions: [pi => pi.on('tool_call', event => { retained = event.input; })],
    tools: [guarded(createWriteTool(root), async call => {
      assert.equal(Object.isFrozen(call.args), true);
      retained.path = 'changed-during-admission.txt';
      await Promise.resolve();
      return { accepted: call.args.path === 'accepted.txt' };
    })] });
  outputs.push([{ type: 'toolCall', id: 'snapshot', name: 'write',
    arguments: { path: 'accepted.txt', content: 'accepted content' } }]);
  await session.prompt('Use admitted arguments');
  assert.equal(await readFile(join(root, 'accepted.txt'), 'utf8'), 'accepted content');
  await assert.rejects(readFile(join(root, 'changed-during-admission.txt')), { code: 'ENOENT' });
});

test('revocation while admission is pending prevents the side effect', async t => {
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-revoke-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const controller = new AbortController();
  const tool = guarded(createWriteTool(root), async () => {
    controller.abort();
    return { accepted: true };
  });
  await assert.rejects(tool.execute('revoked', { path: 'revoked.txt', content: 'no' }, controller.signal),
    { name: 'AbortError' });
  await assert.rejects(readFile(join(root, 'revoked.txt')), { code: 'ENOENT' });
});

for (const decision of [undefined, {}, { accepted: false }, { accepted: 'true' }]) {
  test(`missing or invalid host admission does not execute: ${JSON.stringify(decision)}`, async () => {
    let executed = 0;
    const tool = guarded({ name: 'fixture', execute: async () => { executed++; } }, async () => decision);
    await assert.rejects(tool.execute('invalid', {}), /Host did not admit/);
    assert.equal(executed, 0);
  });
}

test('provider method replacement during admission cannot change the approved execution', async () => {
  const calls = [];
  const provider = { name: 'original', async execute() { calls.push('original'); return 'original'; } };
  const tool = guarded(provider, async call => {
    assert.equal(call.toolName, 'original');
    provider.name = 'replacement';
    provider.execute = async () => { calls.push('replacement'); return 'replacement'; };
    return { accepted: true };
  });
  assert.equal(await tool.execute('stable-provider', {}), 'original');
  assert.equal(await tool.execute('stable-provider-again', {}), 'original');
  assert.deepEqual(calls, ['original', 'original']);
});

test('abort does not erase an already completed side effect or its durable receipt', async t => {
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-abort-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  let entered;
  const running = new Promise(resolve => { entered = resolve; });
  let executed = 0;
  const native = createWriteTool(root);
  const tool = guarded({ ...native, async execute(id, args, signal, update, ...ctx) {
    const result = await native.execute(id, args, signal, update, ...ctx);
    executed++;
    entered();
    if (!signal.aborted) await new Promise(resolve => signal.addEventListener('abort', resolve, { once: true }));
    return result;
  } }, async () => ({ accepted: true }));
  const { session, outputs } = await fixture(t, { root, tools: [tool] });
  outputs.push([{ type: 'toolCall', id: 'abort-after-write', name: 'write',
    arguments: { path: 'actual-receipt.json', content: '{"effect":"completed"}' } }]);
  const pending = session.prompt('Perform one action');
  await running;
  await session.abort();
  await pending;
  assert.equal(executed, 1);
  assert.deepEqual(JSON.parse(await readFile(join(root, 'actual-receipt.json'), 'utf8')), { effect: 'completed' });
  const reopened = SessionManager.open(session.sessionManager.getSessionFile());
  assert.equal(reopened.buildSessionContext().messages.filter(m => m.role === 'toolResult').length, 1);
});

test('all native coding tool providers reach the same final admission seam', async t => {
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-catalog-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const admitted = [], executed = [];
  const tools = createCodingTools(root).map(tool => guarded({ ...tool,
    execute: async (...args) => { executed.push(tool.name); return tool.execute(...args); },
  }, async call => { admitted.push(call.toolName); return { accepted: false }; }));
  const args = { read: { path: 'fixture.txt' }, bash: { command: 'printf fixture' },
    edit: { path: 'fixture.txt', oldText: 'a', newText: 'b' },
    write: { path: 'fixture.txt', content: 'fixture' } };
  assert.deepEqual(tools.map(tool => tool.name).sort(), Object.keys(args).sort());
  const { session, outputs } = await fixture(t, { root, tools });
  outputs.push(tools.map(tool => ({ type: 'toolCall', id: tool.name,
    name: tool.name, arguments: args[tool.name] })));
  await session.prompt('Try available fixture actions');
  assert.deepEqual(admitted.sort(), Object.keys(args).sort());
  assert.deepEqual(executed, []);
  assert.equal(session.messages.at(-1).stopReason, 'stop');
});

test('extension-registered tools receive final host admission and keep their execution context', async t => {
  let executions = 0, checked;
  const extension = pi => pi.registerTool(guarded({ name: 'fixture_lookup', label: 'Fixture lookup',
    description: 'Offline extension tool',
    parameters: { type: 'object', properties: { key: { type: 'string' } }, required: ['key'] },
    async execute(id, args, signal, update, context) {
      assert.equal(typeof context.cwd, 'string');
      assert.equal(args.key, 'resource');
      executions++;
      return { content: [{ type: 'text', text: 'source-backed fixture observation' }] };
    },
  }, async call => { checked = call; return { accepted: true }; }));
  const { session, outputs } = await fixture(t, { extensions: [extension] });
  outputs.push([{ type: 'toolCall', id: 'lookup', name: 'fixture_lookup', arguments: { key: 'resource' } }]);
  await session.prompt('Read an external fixture');
  assert.equal(checked.toolName, 'fixture_lookup');
  assert.equal(executions, 1);
  assert.equal(session.messages.find(m => m.role === 'toolResult').isError, false);
});

test('steering an active real SDK session is persisted with the same task history', async t => {
  let entered, release;
  const started = new Promise(resolve => { entered = resolve; });
  const proceed = new Promise(resolve => { release = resolve; });
  const root = await mkdtemp(join(tmpdir(), 'capstone-bridge-steer-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const native = createWriteTool(root);
  const tool = guarded({ ...native, async execute(...args) {
    entered(); await proceed; return native.execute(...args);
  } }, async () => ({ accepted: true }));
  const { session, outputs } = await fixture(t, { root, tools: [tool] });
  outputs.push([{ type: 'toolCall', id: 'steer-write', name: 'write',
    arguments: { path: 'steer.txt', content: 'result' } }]);
  const pending = session.prompt('Start the task');
  await started;
  try { await session.steer('Include the resource limitations'); }
  finally { release(); }
  await pending;
  const reopened = SessionManager.open(session.sessionManager.getSessionFile());
  const users = reopened.buildSessionContext().messages.filter(m => m.role === 'user');
  assert.equal(users.length, 2);
  assert.match(JSON.stringify(users.at(-1).content), /Include the resource limitations/);
});
