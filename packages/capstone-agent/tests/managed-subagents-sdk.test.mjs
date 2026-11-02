import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createManagedSubagents} from '../src/capstone_agent/resources/managed-subagents.mjs';
import {createManagedChildSession} from '../src/capstone_agent/resources/general-sdk.mjs';

test('real pinned SDK research child has a scoped role and guarded tools without parent workflow or history', async () => {
  const sdkRoot = resolve(import.meta.dirname, '../../../.grid-agent/runtime/pi/source/packages');
  const sdk = await import(pathToFileURL(resolve(sdkRoot, 'coding-agent/dist/index.js')).href);
  const ai = await import(pathToFileURL(resolve(sdkRoot, 'ai/dist/index.js')).href);
  const root = await mkdtemp(resolve(tmpdir(), 'managed-subagents-sdk-'));
  let closes = 0;
  let calls = 0;
  const observed = [];
  const timings = [];
  const originalCwd = process.cwd();
  const originalAgentDir = process.env.PI_CODING_AGENT_DIR;
  try {
    const agentDir = resolve(root, 'private-agent');
    await mkdir(agentDir);
    process.chdir(root);
    process.env.PI_CODING_AGENT_DIR = agentDir;
    await writeFile(resolve(root, 'selected.csv'), 'SOURCE_BYTES_84');
    await mkdir(resolve(root, '.pi', 'extensions'), {recursive: true});
    await writeFile(resolve(root, '.pi', 'extensions', 'forbidden.mjs'), 'throw new Error("disk extension must never load")');
    const model = {id: 'fixed', name: 'Offline', provider: 'capstone-general', api: 'openai-completions',
      baseUrl: 'http://127.0.0.1:1', reasoning: false, input: ['text'], contextWindow: 32000,
      maxTokens: 1024, cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
    const runtime = {getModel: () => model, hasConfiguredAuth: () => true,
      getAuth: async () => ({auth: {apiKey: 'offline-fixture'}}), isUsingOAuth: () => false,
      streamSimple(selected, context) {
        assert.equal(selected.id, model.id);
        assert.doesNotMatch(context.systemPrompt, /PARENT_WORKFLOW_SENTINEL|PARENT_HISTORY_SENTINEL|PARENT_SYSTEM_SENTINEL/);
        assert.match(context.systemPrompt, /untrusted/);
        assert.match(context.systemPrompt, /Authority/);
        assert.match(context.systemPrompt, /parent owns/i);
        assert.match(context.systemPrompt, /external lookup/);
        assert.match(context.systemPrompt, /Host-admitted read-only task source/);
        assert.match(context.systemPrompt, /selected.csv/);
        assert.deepEqual(context.tools.map(tool => tool.name), ['read']);
        const results = context.messages.filter(message => message.role === 'toolResult');
        if (calls === 1) {
          assert.equal(results.at(-1).isError, true);
        }
        if (calls === 2) {
          assert.match(JSON.stringify(results.at(-1).content), /SOURCE_BYTES_84/);
        }
        const content = calls < 2 ? [{type: 'toolCall', id: 'read-' + calls, name: calls === 0 ? 'write' : 'read',
          arguments: {path: calls === 0 ? 'forbidden' : 'selected.csv', ...(calls === 0 ? {content: 'NO'} : {})}}]
          : [{type: 'text', text: 'Actual source gives 84.'}];
        calls++;
        const message = {role: 'assistant', content, api: model.api, provider: model.provider,
          model: model.id, timestamp: Date.now(), stopReason: calls < 3 ? 'toolUse' : 'stop',
          usage: {input: 13, output: 3, cacheRead: 0, cacheWrite: 0, totalTokens: 16,
            cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0}}};
        const stream = ai.createAssistantMessageEventStream();
        stream.push({type: 'done', reason: message.stopReason, message}); stream.end(); return stream;
      }};
    const config = {model: model.id, settings: {packages: [], extensions: [], skills: []},
      extensions: [], allowedSkills: [], contextFiles: [{path:'parent-history',content:'PARENT_HISTORY_SENTINEL'}],
      deliveryReviewSources: [{path:resolve(root,'selected.csv'),file_name:'selected.csv',size_bytes:15,sha256:'a'.repeat(64),origin:'original_input',source_ref:'resource:fixture'}],
      applicationPolicy: {allowed_tools: ['read']},
      systemPrompt: 'PARENT_SYSTEM_SENTINEL',appendSystemPrompt:['PARENT_WORKFLOW_SENTINEL: plan, record and assess the full research task.']};
    const host = createManagedSubagents({createChildSession: async ({signal}) => {
      const owned = await createManagedChildSession(config, sdk, runtime, {toolNames: ['read'], signal, researchExecution:true});
      return {session: owned.session, async close() { try { await owned.close(); } finally { closes++; } }};
    }});
    const result = await host.run({prompt: 'Use only the selected file.', onToolActivity: event => observed.push(event), onModelResponse: event => timings.push(event)});
    assert.equal(result.responseText, 'Actual source gives 84.', JSON.stringify(result));
    assert.equal(result.failure, undefined);
    assert.equal(calls, 3);
    assert.equal(result.usage.length, 3);
    assert.equal(result.turns, 3);
    assert.deepEqual(timings.map(event => event.response_number), [1, 2, 3]);
    assert.ok(timings.every(event => Number.isSafeInteger(event.response_ms) && event.response_ms >= 0));
    assert.equal(closes, 1);
    await assert.rejects(import('node:fs/promises').then(fs => fs.stat(resolve(root, 'forbidden'))), {code: 'ENOENT'});
    assert.ok(observed.some(event => event.type === 'end' && event.isError));
    assert.ok(observed.some(event => event.type === 'end' && event.isError === false));
  } finally {
    process.chdir(originalCwd);
    if (originalAgentDir === undefined) delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR = originalAgentDir;
    await rm(root, {recursive: true, force: true});
  }
});
