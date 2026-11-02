import test from 'node:test';
import assert from 'node:assert/strict';
import {summarizeToolOperation} from '../src/capstone_agent/resources/subagents/managed-runner.mjs';

test('summarizes script intent before bounding the operation preview',()=>{
  const command=`cd /private/${'workspace'.repeat(40)}\npython3 - <<'PY'\n# 计算月度价格并保存指标表\nimport pandas as pd\nPY`;
  assert.equal(summarizeToolOperation('bash',command),'计算月度价格并保存指标表');
  assert.equal(summarizeToolOperation('bash',"cd '/private/task workspace' && python3 analyze.py"),'python3 analyze.py');
  assert.equal(summarizeToolOperation('read','/private/file.csv'),'/private/file.csv');
  assert.equal(summarizeToolOperation('bash','echo ok\n# unrelated later comment'),'echo ok # unrelated later comment');
});

const modulePath = '../src/capstone_agent/resources/managed-subagents.mjs';
async function adapter(options) {
  const module = await import(modulePath);
  return module.createManagedSubagents(options);
}
function child(perform) {
  const listeners = new Set();
  const state = {prompts: [], aborts: 0, closes: 0, steers: []};
  const emit = event => { for (const listener of listeners) listener(event); };
  const session = {
    messages: [],
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    async prompt(prompt) { state.prompts.push(prompt); await perform({emit, session, state}); },
    async abort() { state.aborts++; },
    steer(text) { state.steers.push(text); },
  };
  return {session, state, listeners, close: async () => { state.closes++; }};
}
function answer(emit, session, text, extra = {}) {
  const message = {role: 'assistant', content: [{type: 'text', text}], stopReason: 'stop', ...extra};
  emit({type: 'message_start', message});
  emit({type: 'message_update', assistantMessageEvent: {type: 'text_delta', delta: text}});
  session.messages.push(message);
  emit({type: 'message_end', message});
  emit({type: 'turn_end'});
}

test('host factory supplies the only session; actual output, tools and usage are observed before close', async () => {
  const events = [];
  const fixture = child(async ({emit, session}) => {
    emit({type: 'tool_execution_start', toolName: 'read', toolCallId: 'read-1'});
    emit({type: 'tool_execution_end', toolName: 'read', toolCallId: 'read-1', isError: false});
    answer(emit, session, 'Actual child answer', {usage: {input: 7, output: 4, cacheRead: 2}});
  });
  const host = await adapter({createChildSession: async options => {
    assert.deepEqual(Object.keys(options), ['signal']);
    return fixture;
  }});
  const result = await host.run({prompt: 'Explicit selected task', onToolActivity: e => events.push(e),
    onAssistantUsage: u => events.push(u), onResult: r => {
      assert.equal(fixture.state.closes, 1);
      assert.equal(r.responseText, 'Actual child answer');
    }});
  assert.equal(result.responseText, 'Actual child answer');
  assert.equal(result.turns, 1);
  assert.equal(result.modelResponses, 1);
  assert.equal(result.aborted, false);
  assert.deepEqual(result.usage, [{input: 7, output: 4, cacheRead: 2, cacheWrite: null, totalTokens: null, cost: null}]);
  assert.deepEqual(events[0], {type: 'start', toolName: 'read', toolCallId: 'read-1'});
  assert.deepEqual(events[1], {type: 'end', toolName: 'read', toolCallId: 'read-1', isError: false});
  assert.deepEqual(fixture.state.prompts, ['Explicit selected task']);
  assert.equal(fixture.listeners.size, 0);
});

test('child response timing reports observed turns and does not invent a missing start', async () => {
  const timings = [];
  const fixture = child(async ({emit, session}) => {
    answer(emit, session, 'No observed start');
    emit({type: 'turn_start'});
    answer(emit, session, 'Observed response');
  });
  const host = await adapter({createChildSession: async () => fixture});
  await host.run({prompt: 'Check', onModelResponse: value => timings.push(value)});
  assert.equal(timings.length, 1);
  assert.equal(timings[0].response_number, 2);
  assert.ok(Number.isSafeInteger(timings[0].response_ms) && timings[0].response_ms >= 0);
});

test('pre-aborted tasks never allocate a child', async () => {
  const controller = new AbortController(); controller.abort();
  const host = await adapter({createChildSession: async () => assert.fail('must not allocate')});
  const result = await host.run({prompt: 'task', signal: controller.signal});
  assert.equal(result.aborted, true);
  assert.equal(result.responseText, '');
});

test('absolute work window steers once and drains the same child without resetting on correction', async () => {
  const fixture=child(async ({emit,session,state})=>{
    if(state.prompts.length===1){answer(emit,session,'saved partial');return;}
    await new Promise(resolve=>{fixture.session.abort=async()=>{state.aborts++;resolve();};});
  });
  const now=Date.now(),host=await adapter({createChildSession:async()=>fixture});
  let checks=0;
  const result=await host.run({prompt:'bounded producer',workDeadline:{wrapup_at_ms:now+20,finish_by_ms:now+45},
    settledContinuation:()=>++checks===1?'Correct the declared association':null});
  assert.equal(result.aborted,true);assert.equal(result.budget_exhausted,true);
  assert.equal(fixture.state.steers.length,1);assert.match(fixture.state.steers[0],/not_run|limitations/);
  assert.equal(fixture.state.prompts.length,2);assert.equal(result.modelResponses,1);
  assert.equal(fixture.state.closes,1);assert.equal(fixture.listeners.size,0);
});

test('expired absolute child window allocates no fresh session',async()=>{
  const host=await adapter({createChildSession:async()=>assert.fail('no late launch')});
  const result=await host.run({prompt:'late',workDeadline:{wrapup_at_ms:Date.now()-2,finish_by_ms:Date.now()-1}});
  assert.equal(result.budget_exhausted,true);assert.equal(result.turns,0);assert.equal(result.aborted,true);
});
test('a completed wrap-up preserves native completion and starts no correction prompt',async()=>{
  const fixture=child(async({emit,session})=>{await new Promise(resolve=>setTimeout(resolve,25));answer(emit,session,'Useful partial output retained');});
  const host=await adapter({createChildSession:async()=>fixture}),now=Date.now();
  const result=await host.run({prompt:'Save current work',workDeadline:{wrapup_at_ms:now+5,finish_by_ms:now+200},
    settledContinuation:()=> 'Missing optional slot; do not start more work'});
  assert.equal(result.aborted,false);assert.equal(result.work_steered,true);
  assert.equal(result.modelResponses,1);assert.equal(fixture.state.prompts.length,1);assert.equal(fixture.state.closes,1);
});
test('factory crossing the deadline closes without any late first prompt or invented usage',async()=>{
  const realNow=Date.now;let now=1000;Date.now=()=>now;
  try{
    const fixture=child(async({emit,session})=>answer(emit,session,'Too late'));
    const host=await adapter({createChildSession:async()=>{now=3000;return fixture;}});
    const result=await host.run({prompt:'bounded',workDeadline:{wrapup_at_ms:1500,finish_by_ms:2000}});
    assert.equal(fixture.state.prompts.length,0);assert.equal(result.aborted,true);assert.equal(result.budget_exhausted,true);
    assert.equal(result.modelResponses,0);assert.deepEqual(result.usage,[]);assert.equal(fixture.state.closes,1);
  }finally{Date.now=realNow;}
});
test('correction preflight crossing the deadline cannot send a late prompt or cancel completed native work',async()=>{
  const realNow=Date.now;let now=1000;Date.now=()=>now;
  try{
    const fixture=child(async({emit,session})=>answer(emit,session,'Saved actual work',{usage:{input:2,output:3}}));
    const host=await adapter({createChildSession:async()=>fixture});let checks=0;
    const result=await host.run({prompt:'bounded',workDeadline:{wrapup_at_ms:1500,finish_by_ms:2000},
      settledContinuation:async()=>{now=3000;return ++checks===1?'Correct association':null;}});
    assert.equal(fixture.state.prompts.length,1);assert.equal(result.aborted,false);assert.equal(result.budget_exhausted,true);
    assert.equal(result.modelResponses,1);assert.equal(result.usage.length,1);assert.equal(fixture.state.closes,1);
  }finally{Date.now=realNow;}
});
test('confirmed host finalization crossing the child deadline retains true native completion',async()=>{
  const fixture=child(async({emit,session})=>answer(emit,session,'Saved actual work'));
  const host=await adapter({createChildSession:async()=>fixture}),now=Date.now();
  const result=await host.run({prompt:'bounded',workDeadline:{wrapup_at_ms:now+5,finish_by_ms:now+15},
    settledContinuation:async()=>{await new Promise(resolve=>setTimeout(resolve,25));return null;}});
  assert.equal(result.aborted,false);assert.equal(result.budget_exhausted,true);
  assert.equal(fixture.state.aborts,0);assert.equal(fixture.state.prompts.length,1);assert.equal(fixture.state.closes,1);
});

test('child tool diagnostics reach the private host before session close', async () => {
  const events = [];
  const args = {command: 'python analysis.py'};
  const result = {content: [{type: 'text', text: 'ModuleNotFoundError: scipy'}]};
  const fixture = child(async ({emit, session}) => {
    emit({type: 'tool_execution_start', toolName: 'bash', toolCallId: 'b1', args});
    emit({type: 'tool_execution_end', toolName: 'bash', toolCallId: 'b1', isError: true, result});
    answer(emit, session, 'Analysis incomplete');
  });
  const host = await adapter({createChildSession: async () => fixture});
  await host.run({prompt: 'Analyse', onToolActivity: event => events.push(event)});
  assert.deepEqual(events[0].args, args);
  assert.deepEqual(events[1].result, result);
  assert.equal(events[1].isError, true);
});

test('cancellation during factory setup closes the child without prompting', async () => {
  const controller = new AbortController();
  const fixture = child(async () => assert.fail('must not prompt'));
  const host = await adapter({createChildSession: async () => {
    controller.abort(); return fixture;
  }});
  assert.equal((await host.run({prompt: 'task', signal: controller.signal})).aborted, true);
  assert.equal(fixture.state.aborts, 1);
  assert.equal(fixture.state.closes, 1);
});

test('active cancellation forwards abort and always releases listeners/session', async () => {
  const controller = new AbortController();
  const fixture = child(async () => { controller.abort(); });
  const host = await adapter({createChildSession: async () => fixture});
  assert.equal((await host.run({prompt: 'task', signal: controller.signal})).aborted, true);
  assert.equal(fixture.state.aborts, 1);
  assert.equal(fixture.state.closes, 1);
  assert.equal(fixture.listeners.size, 0);
});

test('provider failure preserves partial text and does not replay previous answers', async () => {
  const fixture = child(async ({emit, session}) => {
    answer(emit, session, 'Partial', {stopReason: 'error', errorMessage: 'provider failed'});
  });
  fixture.session.messages.push({role: 'assistant', content: [{type: 'text', text: 'OLD'}]});
  const host = await adapter({createChildSession: async () => fixture});
  const result = await host.run({prompt: 'task'});
  assert.equal(result.failure, 'provider failed');
  assert.equal(result.responseText, 'Partial');
  assert.equal(fixture.state.closes, 1);
});

test('empty new turn cannot return an old answer and thrown failure still closes', async () => {
  const fixture = child(async () => {});
  fixture.session.messages.push({role: 'assistant', content: [{type: 'text', text: 'OLD'}]});
  const host = await adapter({createChildSession: async () => fixture});
  assert.equal((await host.run({prompt: 'task'})).responseText, '');
  const failed = child(async () => { throw new Error('offline failure'); });
  const failHost = await adapter({createChildSession: async () => failed});
  await assert.rejects(failHost.run({prompt: 'task'}), /offline failure/);
  assert.equal(failed.state.closes, 1);
  assert.equal(failed.state.aborts, 1);
  assert.equal(failed.listeners.size, 0);
});

test('upstream turn limit steers once then aborts at host-selected grace limit', async () => {
  const fixture = child(async ({emit}) => { for (let i = 0; i < 3; i++) emit({type: 'turn_end'}); });
  const host = await adapter({createChildSession: async () => fixture, maxTurns: 1, graceTurns: 2});
  const result = await host.run({prompt: 'task'});
  assert.equal(result.aborted, true);
  assert.equal(result.steered, true);
  assert.equal(fixture.state.steers.length, 1);
  assert.equal(fixture.state.aborts, 1);
});

test('concurrent runs retain separate output, cancellation and usage', async () => {
  let release;
  const waiting = new Promise(resolve => { release = resolve; });
  const controller = new AbortController();
  const first = child(async ({emit, session}) => {
    await waiting;
    answer(emit, session, 'FIRST', {usage: {input: 1, output: 2}});
  });
  const second = child(async ({emit, session}) => {
    controller.abort();
    answer(emit, session, 'SECOND', {usage: {input: 7, output: 8}});
    release();
  });
  let allocations = 0;
  const host = await adapter({createChildSession: async () => ++allocations === 1 ? first : second});
  const [a, b] = await Promise.all([host.run({prompt: 'first'}), host.run({prompt: 'second', signal: controller.signal})]);
  assert.equal(a.responseText, 'FIRST');
  assert.equal(a.aborted, false);
  assert.equal(a.usage[0].input, 1);
  assert.equal(b.responseText, 'SECOND');
  assert.equal(b.aborted, true);
  assert.equal(b.usage[0].input, 7);
  assert.equal(first.state.aborts, 0);
  assert.equal(second.state.aborts, 1);
  assert.equal(first.state.closes, 1);
  assert.equal(second.state.closes, 1);
});

test('callback failure aborts and closes; close failure is not reported as success', async () => {
  const fixture = child(async ({emit}) => emit({type: 'turn_end'}));
  const host = await adapter({createChildSession: async () => fixture});
  await assert.rejects(host.run({prompt: 'task', onTurnEnd: () => { throw new Error('receipt failed'); }}), /receipt failed/);
  assert.equal(fixture.state.closes, 1);
  assert.equal(fixture.state.aborts, 1);
  const failedClose = child(async () => {});
  failedClose.close = async () => { throw new Error('close failed'); };
  const closingHost = await adapter({createChildSession: async () => failedClose});
  await assert.rejects(closingHost.run({prompt: 'task', onResult: () => assert.fail('must not report success')}), /close failed/);
});

test('empty token-limit stop is a failure; partial token-limit output is retained', async () => {
  for (const text of ['', 'partial answer']) {
    const fixture = child(async ({emit, session}) => answer(emit, session, text, {stopReason: 'length'}));
    const host = await adapter({createChildSession: async () => fixture});
    const result = await host.run({prompt: 'task'});
    assert.equal(result.responseText, text);
    if (!text) assert.match(result.failure, /token limit/);
    else assert.equal(result.failure, undefined);
  }
});

test('actual assistant responses are counted even when provider usage is missing', async () => {
  const fixture = child(async ({emit, session}) => answer(emit, session, 'No usage supplied'));
  const host = await adapter({createChildSession: async () => fixture});
  const result = await host.run({prompt: 'task'});
  assert.equal(result.modelResponses, 1);
  assert.equal(result.usage.length, 0);
});

test('child output-limit failure retains safe actual finish metadata and observed usage',async()=>{
  const owned=child(({emit,session})=>{session.model={maxTokens:65536};answer(emit,session,'',{stopReason:'length',usage:{input:137885,output:65536,reasoning:65536,cacheRead:0,cacheWrite:0,totalTokens:203421}});});
  const runner=await adapter({createChildSession:async()=>owned,maxTurns:10,graceTurns:1});
  const result=await runner.run({prompt:'Review saved content'});
  assert.equal(result.finish.stop_reason,'length');assert.equal(result.finish.visible_text_chars,0);
  assert.equal(result.finish.reasoning_tokens,65536);assert.equal(result.finish.model_output_capacity,65536);
  assert.equal(result.finish.effective_output_limit,null);assert.equal(result.usage[0].output,65536);
  assert.match(result.failure,/output token limit/);assert.equal(result.modelResponses,1);
});
