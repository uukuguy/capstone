import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, realpath, rename, rm, stat, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

async function fixture(t, { progress = false, runtimeLimits, runtimeLimitMode, getControllerState, isRecordVisible, state = { research_id: "research-1", revision: 1, goal: "Check the selected model", condition_refs: [], claims: [], notes: [], open_questions: [] } } = {}) {
  const root = await realpath(await mkdtemp(join(tmpdir(), "capability-research-")));
  t.after(() => rm(root, { recursive: true, force: true }));
  const binding = { schema_version: "capability-research-channel/1.0", run_id: "run-1", turn_id: "turn-1", attempt_id: "attempt-1", research_id: "research-1", read_tool_schema: {
    type: "object", additionalProperties: false, properties: { section: { type: "string", enum: ["overview", "claims", "notes", "questions", "receipt"] },
      request_id: { anyOf: [{ type: "string", pattern: "^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$" }, { type: "null" }], default: null },
      offset: { type: "integer", minimum: 0 }, limit: { type: "integer", minimum: 1, maximum: 8 } },
  }, update_tool_schema: {
    type: "object", additionalProperties: false, required: ["expected_revision", "changes"], properties: {
      expected_revision: { type: "integer", minimum: 0 },
      changes: { type: "object", additionalProperties: false, properties: { goal: { type: "string", minLength: 1, maxLength: 4000 } }, minProperties: 1 },
    },
  }, depth_tool_schema: { type: "object", additionalProperties: false, required: ["level"],
    properties: { level: { type: "string", enum: ["off", "high"] } } } };
  const view = { ...binding, schema_version: "capability-research-view/1.0", research_revision: state?.revision ?? 0, state };
  if (runtimeLimits) binding.runtime_limits=runtimeLimits;
  delete view.update_tool_schema;
  delete view.read_tool_schema;
  delete view.depth_tool_schema;
  await mkdir(join(root, "requests"));
  await mkdir(join(root, "receipts"));
  await writeFile(join(root, "binding.json"), JSON.stringify(binding));
  if (progress) {
    binding.progress_tool_schema = { type: "object", additionalProperties: false, required: ["kind", "text"],
      properties: { kind: { type: "string", enum: ["goal", "observation", "adjustment", "limitation"] },
        text: { type: "string", minLength: 1, maxLength: 1000 }, refs: { type: "array", maxItems: 32, items: { type: "string", minLength: 1, maxLength: 256 } },
        step_id: { type: "string", pattern: "^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$" }, phase: { type: "string", enum: ["started", "updated", "completed"] } } };
    await writeFile(join(root, "binding.json"), JSON.stringify(binding));
  }
  await writeFile(join(root, "view.json"), JSON.stringify(view));
  const tools = new Map(), handlers = new Map(), failures = [];
  let thinking = "off";
  const { configureResearchTools } = await import("../src/research-tools.mjs");
  const client = configureResearchTools({ registerTool: tool => tools.set(tool.name, tool), on: (name, handler) => handlers.set(name, handler),
    getThinkingLevel: () => thinking, setThinkingLevel: level => { thinking = level; } }, root, {
    timeoutMs: 1000, getControllerState, isRecordVisible, runtimeLimitMode, fatal: message => { failures.push(message); throw new Error("research request blocked"); },
  });
  return { root, binding, view, tools, handlers, failures, client, thinking: () => thinking };
}

test('private dispatch checkpoints never enter automatic research summaries, including debug mode',async t=>{
  const state={research_id:'research-1',revision:1,goal:'Study',claims:[],condition_refs:[],open_questions:[],notes:[
    {note_id:'runtime.dispatch.owner.result',text:'PRIVATE_RESULT'.repeat(8000)},
    {note_id:'runtime.checkpoint.owner.plan',text:'PRIVATE_PLAN'},
    {note_id:'user-note',text:'Keep this observation'},
  ]};
  const f=await fixture(t,{state,runtimeLimitMode:'debug',runtimeLimits:{research_summary_chars:65536}});
  const automatic=await f.handlers.get('context')({messages:[]});
  const text=JSON.stringify(automatic);
  assert.ok(text.includes('Keep this observation'));
  assert.ok(!text.includes('PRIVATE_RESULT'));assert.ok(!text.includes('PRIVATE_PLAN'));
  assert.equal(f.view.state.notes[0].text,'PRIVATE_RESULT'.repeat(8000),'original dispatch record is retained');
});

test('application visibility filters model reads without removing protected records or changing legacy reads',async t=>{
  const state={research_id:'research-1',revision:1,goal:'Study',claims:[],condition_refs:[],open_questions:[],notes:[
    {note_id:'runtime.checkpoint.owner',text:'PRIVATE_CHECKPOINT'},
    {note_id:'result-note',text:'Observed coverage'},
  ]};
  const f=await fixture(t,{state,isRecordVisible:(section,item)=>section!=='notes'||!item.note_id.startsWith('runtime.')});
  const reply=await f.tools.get('agent_research_read').execute('read-notes',{section:'notes'});
  assert.equal(reply.details.ok,true);assert.equal(reply.details.result.total,1);
  assert.deepEqual(reply.details.result.records,[state.notes[1]]);
  assert.equal(JSON.parse(await readFile(join(f.root,'view.json'),'utf8')).state.notes.length,2);
  const legacy=await fixture(t,{state});
  assert.equal((await legacy.tools.get('agent_research_read').execute('read-legacy',{section:'notes'})).details.result.total,2);
});

test('overview preserves current controller identity while bounded ledger history stays separate',async t=>{
  const cycle={phase:'assessing',round:4,pending_action:{id:'cycle-'+ 'a'.repeat(64),questions:['Accepted question'],expected_outputs:['Output'],checks:['Check']},checkpoint:{ref:'checkpoint',revision:1}};
  const state={research_id:'research-1',revision:1,goal:'Study',notes:[{note_id:'runtime.checkpoint.private',text:'PROTECTED_CHECKPOINT_PAYLOAD'}],claims:Array.from({length:20},(_,i)=>({claim_id:'c'+i,statement:'Large historical claim '.repeat(40),refs:[]})),condition_refs:[],open_questions:[]};
  const f=await fixture(t,{state,runtimeLimits:{research_summary_chars:2000},getControllerState:async()=>cycle});
  const overview=await f.tools.get('agent_research_read').execute('overview',{section:'overview'});
  assert.equal(overview.details.ok,true);assert.deepEqual(overview.details.result.cycle,cycle);
  assert.ok(!JSON.stringify(overview).includes('PROTECTED_CHECKPOINT_PAYLOAD'));
  assert.ok(overview.details.result.coverage.omitted.claims>0);
  overview.details.result.cycle.pending_action.questions.length=0;
  assert.deepEqual(cycle.pending_action.questions,['Accepted question']);
  const legacy=await fixture(t,{state});
  const result=await legacy.tools.get('agent_research_read').execute('legacy',{section:'overview'});
  assert.ok(!Object.hasOwn(result.details.result,'cycle'));
});

test('long accepted action keeps automatic summary bounded and explicit overview complete',async t=>{
  const question='Q'.repeat(70000),purpose='P'.repeat(70000);
  const cycle={phase:'assessing',round:4,pending_action:{id:'cycle-'+ 'a'.repeat(64),kind:'assess',objective_id:'current',attempt_id:'attempt-1',round:4,purpose,questions:[question],expected_outputs:['Output'],checks:['Check'],derived_from:[]},next_action:purpose,checkpoint:{ref:'checkpoint',revision:1},update_pending:false};
  const f=await fixture(t,{getControllerState:async()=>cycle});
  const automatic=await f.handlers.get('context')({messages:[]});
  const text=automatic.messages[0].content,summary=JSON.parse(text.slice(text.indexOf('\n')+1));
  assert.ok(Array.from(text).length<=65536);
  assert.equal(summary.cycle.pending_action.id,cycle.pending_action.id);
  assert.ok(!Object.hasOwn(summary.cycle.pending_action,'questions'),'no excerpt can impersonate exact accepted questions');
  assert.equal(summary.cycle.coverage.omitted.questions,1);
  assert.equal(summary.cycle.coverage.omitted.question_chars,70000);
  assert.match(summary.cycle.coverage.recovery,/overview/);
  await f.handlers.get('before_model_request')(modelRequest(automatic.messages));
  const overview=await f.tools.get('agent_research_read').execute('overview',{section:'overview'});
  assert.equal(overview.details.ok,true);assert.deepEqual(overview.details.result.cycle,cycle);
  assert.equal(overview.details.result.cycle.pending_action.questions[0],question);
  const small=await fixture(t,{runtimeLimits:{research_response_bytes:12000},getControllerState:async()=>cycle});
  const refused=await small.tools.get('agent_research_read').execute('overview',{section:'overview'});
  assert.equal(refused.details.ok,false);assert.equal(refused.details.error.code,'capacity_exceeded');
});

test('host runtime client uses existing validation and returns detached committed state',async t=>{
  const f=await fixture(t);
  const view=f.client.readResearch();view.state.goal='Changed locally';
  assert.equal(f.client.readResearch().state.goal,'Check the selected model');
  const rejected=await f.client.commitResearch('host-checkpoint',{expected_revision:1,changes:{unknown:'invalid'}});
  assert.equal(rejected.details.ok,false);
  assert.equal(rejected.details.error.code,'invalid_arguments');
  assert.deepEqual(await readdir(join(f.root,'requests')),[]);
});

test('research reader consumes binding response override above the former 2MiB ceiling',async t=>{
  const state={research_id:'research-1',revision:1,goal:'Study',notes:[{note_id:'large',text:'x'.repeat(2200000)}],claims:[],condition_refs:[],open_questions:[]};
  const f=await fixture(t,{state,runtimeLimits:{research_response_bytes:3000000}});
  const result=await f.tools.get('agent_research_read').execute('large-read',{section:'notes'});
  assert.equal(result.details.ok,true);
  assert.equal(result.details.result.records[0].text.length,2200000);
});

function modelRequest(messages) {
  return { context: { messages: messages.map(message => message.role === "custom"
    ? { role: "user", content: [{ type: "text", text: message.content }] } : message) } };
}

test('receipt lookup explains missing and unknown request identities', async t => {
  const f = await fixture(t);
  const tool = f.tools.get('agent_research_read');
  const missing = await tool.execute('missing', {section: 'receipt'});
  assert.equal(missing.details.error.code, 'invalid_arguments');
  assert.match(missing.details.error.message, /request_id.*agent_research_update/);
  const unknown = await tool.execute('unknown', {section: 'receipt', request_id: 'cycle-example'});
  assert.equal(unknown.details.error.code, 'research_request_not_found');
  assert.match(unknown.details.error.message, /not a research cycle/);
  assert.equal(unknown.details.error.message.includes(f.root), false);
});

test("research rejection uses the SDK result hook without dropping its receipt", async t => {
  const f = await fixture(t, { progress: true });
  const result = await f.tools.get("agent_research_read").execute("bad-read", { section: "receipt", request_id: null });
  const event = { toolName: "agent_research_read", isError: false, content: result.content, details: result.details };
  const patched = { ...event, ...await f.handlers.get("tool_result")(event) };
  assert.equal(patched.isError, true);
  assert.equal(patched.details.error.code, result.details.error.code);
  assert.deepEqual(patched.content, result.content);
  assert.equal(await f.handlers.get("tool_result")({ toolName: "bash", details: { ok: false } }), undefined);
  assert.equal(await f.handlers.get("tool_result")({ toolName: "agent_research_read", details: { ok: true }, isError: false }), undefined);
});

test("managed Pi applies research failure to the finalized tool result", async t => {
  const f = await fixture(t);
  const repository = resolve(import.meta.dirname, "../../..");
  const source = (await readFile(join(repository, ".grid-agent/runtime/pi/active"), "utf8")).split("\n")[0];
  const agentDir = join(f.root, "agent"), cwd = join(f.root, "work");
  await mkdir(join(agentDir, "extensions"), { recursive: true });
  await mkdir(cwd);
  const extension = pathToFileURL(join(repository, "packages/pi-capability-tools/src/research-tools.mjs")).href;
  await writeFile(join(agentDir, "extensions/research.ts"),
    `import { configureResearchTools } from ${JSON.stringify(extension)};\nexport default pi => configureResearchTools(pi, ${JSON.stringify(f.root)});\n`);
  const runtimeImport = name => import(pathToFileURL(join(source, "packages/coding-agent/dist/core", `${name}.js`)));
  const [{ createAgentSession }, { ModelRuntime }, { SettingsManager }, { SessionManager }] = await Promise.all([
    runtimeImport("sdk"), runtimeImport("model-runtime"), runtimeImport("settings-manager"), runtimeImport("session-manager"),
  ]);
  const modelRuntime = await ModelRuntime.create({ authPath: join(agentDir, "auth.json"), modelsPath: null, refreshOnCreate: false });
  modelRuntime.streamSimple = () => { throw new Error("contract test must not call a provider"); };
  const { session, extensionsResult } = await createAgentSession({ cwd, agentDir, modelRuntime,
    noTools: "builtin", settingsManager: SettingsManager.inMemory({}), sessionManager: SessionManager.inMemory(cwd) });
  t.after(() => session.dispose());
  assert.deepEqual(extensionsResult.errors, []);
  const tool = extensionsResult.extensions[0].tools.get("agent_research_read").definition;
  const args = { section: "receipt", request_id: null };
  const result = await tool.execute("invalid-receipt", args);
  // agent-core starts non-throwing results with isError=false. Verify the real
  // AgentSession extension bridge corrects it before events/model persistence.
  const finalized = await session.agent.afterToolCall({ toolCall: { id: "invalid-receipt", name: tool.name }, args, result, isError: false });
  assert.equal(finalized.isError, true);
  assert.deepEqual(finalized.content, result.content);
});

test("research reads accept the published nullable request identity outside receipt lookup", async t => {
  const f = await fixture(t);
  const tool = f.tools.get("agent_research_read");
  for (const section of ["overview", "claims", "notes", "questions"]) {
    assert.equal((await tool.execute("read-" + section, { section, request_id: null })).details.ok, true);
  }
  assert.equal((await tool.execute("read-receipt", { section: "receipt", request_id: null })).isError, true);
  assert.equal((await tool.execute("read-invalid", { section: "overview", request_id: "request-1" })).isError, true);
});

test("task progress records explicit public work without research creation or evidence", async t => {
  const f = await fixture(t, { progress: true, state: null });
  const tool = f.tools.get("agent_task_progress");
  const result = await tool.execute("progress-1", { kind: "goal", text: "检查故障区域。" });
  assert.equal(result.details.ok, true);
  assert.deepEqual(result.details.result, { kind: "goal", text: "检查故障区域。", refs: [] });
  assert.deepEqual(result.details.evidence_refs, []);
  assert.deepEqual(await readdir(join(f.root, "requests")), []);
  assert.equal((await tool.execute("progress-2", { kind: "verified", text: "结论" })).isError, true);
  assert.equal((await tool.execute("progress-3", { kind: "goal", text: "目标", thread_id: "other" })).isError, true);
  assert.equal((await tool.execute("progress-4", { kind: "goal", text: "目标", step_id: "inspect" })).isError, true);
  assert.equal((await tool.execute("progress-5", { kind: "goal", text: "目标", step_id: "inspect", phase: "started" })).details.ok, true);
  const paired = await tool.execute("progress-pair", { kind: "goal", text: "目标", step_id: "inspect" });
  assert.match(paired.details.error.message, /step_id and phase.*together/);
  const invalid = await tool.execute("progress-invalid", { kind: "PRIVATE_VALUE", text: "目标" });
  assert.match(invalid.details.error.message, /kind.*goal.*observation.*adjustment.*limitation/);
  assert.match(invalid.details.error.message, /purpose/);
  assert.doesNotMatch(JSON.stringify(invalid), /PRIVATE_VALUE/);
});

async function pending(root) {
  for (let i = 0; i < 100; i++) {
    const names = (await readdir(join(root, "requests"))).filter(name => name.endsWith(".json"));
    if (names.length) {
      const raw = await readFile(join(root, "requests", names[0]));
      return { name: names[0], raw, request: JSON.parse(raw) };
    }
    await delay(5);
  }
  throw new Error("update request was not published");
}

test('published requests retain their immutable inode through cleanup and exact replay', async t => {
  const f = await fixture(t);
  const args = { expected_revision: 1, changes: { goal: 'Updated goal' } };
  const waiting = f.client.commitResearch('stable-publication', args);
  const input = await pending(f.root);
  await acknowledge(f, input);
  assert.equal((await waiting).details.ok, true);
  const path = join(f.root, 'requests', input.name), first = await stat(path, { bigint: true });
  assert.equal(first.nlink, 2n, 'hidden anchor must stay linked until whole-task cleanup');
  const replay = await f.client.commitResearch('stable-publication', args);
  assert.equal(replay.details.ok, true);
  const second = await stat(path, { bigint: true });
  assert.equal(second.ino, first.ino); assert.equal(second.ctimeNs, first.ctimeNs);
  assert.equal((await readFile(path)).toString(), input.raw.toString());
  assert.equal((await readdir(join(f.root, 'requests'))).filter(name => name.endsWith('.tmp')).length, 1);
});

test('debug capacity escapes research tool repair and never publishes an oversized request',async t=>{
  const f=await fixture(t,{runtimeLimits:{research_request_bytes:10},runtimeLimitMode:'debug'});
  await assert.rejects(f.client.commitResearch('oversized',{expected_revision:1,changes:{goal:'Updated'}}),
    error=>error.capacity?.mode==='debug'&&error.capacity.dimension==='research_request_bytes');
  assert.deepEqual(await readdir(join(f.root,'requests')),[]);
});

async function acknowledge(f, input, { status = "committed", digest, updateView = true } = {}) {
  const ack = { schema_version: "capability-research-receipt/1.0", run_id: "run-1", turn_id: "turn-1", attempt_id: "attempt-1", request_id: input.request.request_id,
    request_sha256: digest ?? createHash("sha256").update(input.raw).digest("hex"), status,
    receipt: { research_id: "research-1", request_id: input.request.request_id, research_revision: input.request.expected_revision + 1, event_sequence: 3 },
  };
  if (status === "committed" && updateView) {
    f.view.research_revision = ack.receipt.research_revision;
    f.view.state.revision = ack.receipt.research_revision;
    f.view.state.goal = input.request.changes.goal;
    await writeFile(join(f.root, "view.json"), JSON.stringify(f.view));
  }
  // Match the host's atomic publication: readers must never see partial JSON.
  const receiptPath = join(f.root, "receipts", input.name);
  await writeFile(receiptPath + ".tmp", JSON.stringify(ack));
  await rename(receiptPath + ".tmp", receiptPath);
}

test("registers bounded research read and update tools without identity or path arguments", async t => {
  const f = await fixture(t);
  assert.deepEqual([...f.tools.keys()], ["agent_research_read", "agent_research_update", "agent_research_depth"]);
  assert.deepEqual(Object.keys(f.tools.get("agent_research_update").parameters.properties), ["expected_revision", "changes"]);
  const result = await f.tools.get("agent_research_update").execute("tool-1", { expected_revision: 1, changes: { goal: "New" }, research_id: "other" });
  assert.equal(result.isError, true);
  assert.deepEqual(await readdir(join(f.root, "requests")), []);
});

test("reasoning depth is adaptive, recorded as a core result, and cannot change providers", async t => {
  const f = await fixture(t);
  const tool = f.tools.get("agent_research_depth");
  const result = await tool.execute("depth-1", { level: "high" });
  assert.equal(result.details.ok, true);
  assert.deepEqual(result.details.result, { previous_level: "off", requested_level: "high", applied_level: "high" });
  assert.equal(f.thinking(), "high");
  assert.equal((await tool.execute("depth-2", { level: "off" })).details.ok, true);
  assert.equal(f.thinking(), "off");
  assert.equal((await tool.execute("depth-3", { level: "high", provider: "other" })).isError, true);
  assert.equal(f.thinking(), "off");
  assert.deepEqual(await readdir(join(f.root, "requests")), []);
  const cancelled = new AbortController();
  cancelled.abort();
  assert.equal((await tool.execute("depth-4", { level: "high" }, cancelled.signal)).details.error.code, "cancelled");
  assert.equal(f.thinking(), "off");
});

test("returns paged research records with explicit coverage and no Authority evidence", async t => {
  const f = await fixture(t);
  f.view.state.claims = Array.from({ length: 12 }, (_, i) => ({ claim_id: `claim-${i}`, statement: `Observation ${i}`, status: "pending", refs: [] }));
  await writeFile(join(f.root, "view.json"), JSON.stringify(f.view));
  const result = await f.tools.get("agent_research_read").execute("read-1", { section: "claims", offset: 8, limit: 4 });
  assert.equal(result.details.result.total, 12);
  assert.equal(result.details.result.records.length, 4);
  assert.equal(result.details.result.next_offset, null);
  assert.deepEqual(result.details.evidence_refs, []);
});

test("preserves the host rejection reason so the next update can repair it", async t => {
  const f = await fixture(t);
  const waiting = f.tools.get("agent_research_update").execute("tool-rejected", { expected_revision: 1, changes: { goal: "Updated goal" } });
  const input = await pending(f.root);
  await writeFile(join(f.root, "receipts", input.name), JSON.stringify({
    schema_version: "capability-research-receipt/1.0", run_id: "run-1", turn_id: "turn-1", attempt_id: "attempt-1",
    request_id: input.request.request_id, request_sha256: createHash("sha256").update(input.raw).digest("hex"),
    status: "rejected", code: "research_goal_required", message: "The first research update requires changes.goal; no update was committed.",
  }));
  const result = await waiting;
  assert.equal(result.isError, true);
  assert.equal(result.details.error.message, "The first research update requires changes.goal; no update was committed.");
  assert.equal(result.details.error.phase, "validate");
  assert.equal(f.view.research_revision, 1);
});

test("does not report update success until a matching durable receipt arrives", async t => {
  const f = await fixture(t);
  let settled = false;
  const waiting = f.tools.get("agent_research_update").execute("tool-1", { expected_revision: 1, changes: { goal: "Updated goal" } }).then(result => { settled = true; return result; });
  const input = await pending(f.root);
  assert.equal(settled, false);
  assert.equal("research_id" in input.request, false);
  await acknowledge(f, input);
  const result = await waiting;
  assert.equal(result.isError, undefined);
  assert.equal(result.details.result.receipt.research_revision, 2);
});

test("preserves a confirmed commit when the published view is stale", async t => {
  const f = await fixture(t);
  const waiting = f.tools.get("agent_research_update").execute("tool-1", { expected_revision: 1, changes: { goal: "Updated" } });
  await acknowledge(f, await pending(f.root), { updateView: false });
  const result = await waiting;
  assert.equal(result.isError, true);
  assert.equal(result.details.error.code, "research_view_not_ready");
  assert.equal(result.details.result.status, "committed");
  assert.equal(result.details.result.receipt.research_revision, 2);
  assert.equal(result.details.result.view_ready, false);
  await assert.rejects(f.handlers.get("before_model_request")({ context: { messages: [] } }), /research request blocked/);
});

test("rejects a mismatched receipt fingerprint", async t => {
  const f = await fixture(t);
  const waiting = f.tools.get("agent_research_update").execute("tool-1", { expected_revision: 1, changes: { goal: "Updated" } });
  await acknowledge(f, await pending(f.root), { digest: "0".repeat(64) });
  const result = await waiting;
  assert.equal(result.isError, true);
  assert.equal(result.details.error.code, "research_receipt_mismatch");
});

test("cancellation after publication reports an unconfirmed outcome", async t => {
  const f = await fixture(t);
  const abort = new AbortController();
  const waiting = f.tools.get("agent_research_update").execute("tool-1", { expected_revision: 1, changes: { goal: "Updated" } }, abort.signal);
  await pending(f.root);
  abort.abort();
  const result = await waiting;
  assert.equal(result.details.error.code, "research_outcome_not_confirmed");
  assert.equal(result.details.result.status, "not_confirmed");
});

test("an unconfirmed update can be checked by its opaque request id without resubmitting", async t => {
  const f = await fixture(t);
  const abort = new AbortController();
  const waiting = f.tools.get("agent_research_update").execute("tool-1", { expected_revision: 1, changes: { goal: "Updated" } }, abort.signal);
  const input = await pending(f.root);
  abort.abort();
  const uncertain = await waiting;
  await acknowledge(f, input);
  const lookup = await f.tools.get("agent_research_read").execute("lookup", { section: "receipt", request_id: uncertain.details.result.request_id });
  assert.equal(lookup.isError, undefined);
  assert.equal(lookup.details.result.status, "committed");
  assert.equal((await readdir(join(f.root, "requests"))).filter(name => name.endsWith(".json")).length, 1);
});

test("context restores the latest state once after compaction and keeps the user request", async t => {
  const f = await fixture(t);
  const user = { role: "user", content: "Continue this research" };
  const first = await f.handlers.get("context")({ messages: [user] });
  const second = await f.handlers.get("context")({ messages: first.messages });
  assert.equal(second.messages.length, 2);
  assert.equal(second.messages[0], user);
  f.view.research_revision = f.view.state.revision = 2;
  f.view.state.goal = "Changed after the checkpoint";
  await writeFile(join(f.root, "view.json"), JSON.stringify(f.view));
  const restored = await f.handlers.get("context")({ messages: [{ role: "user", content: "Compacted history" }, user] });
  assert.match(restored.messages.at(-1).content, /Changed after the checkpoint/);
  await f.handlers.get("before_model_request")(modelRequest(restored.messages));
});

test("request boundary blocks a missing context hook and stale restored input", async t => {
  const f = await fixture(t);
  await assert.rejects(f.handlers.get("before_model_request")(modelRequest([{ role: "user", content: "Continue" }])), /blocked/);
  const injected = await f.handlers.get("context")({ messages: [] });
  f.view.research_revision = f.view.state.revision = 2;
  await writeFile(join(f.root, "view.json"), JSON.stringify(f.view));
  await assert.rejects(f.handlers.get("before_model_request")(modelRequest(injected.messages)), /blocked/);
});

test("graph request validates its prepared immutable snapshot while child checkpoints advance", async t => {
  let revision = 1;
  const f = await fixture(t, {getControllerState: () => ({graph: {
    schema: 'capstone-enterprise-graph/2', graph_ref: 'graph:' + revision},
    checkpoint: {ref: 'checkpoint:' + revision, revision}})});
  const first = await f.handlers.get('context')({messages: [{role: 'user', content: 'Continue'}]});
  revision = 2;
  f.view.research_revision = f.view.state.revision = 2;
  f.view.state.notes.push({note_id: 'runtime.checkpoint.two', text: 'Committed child settlement'});
  await writeFile(join(f.root, 'view.json'), JSON.stringify(f.view));
  await f.handlers.get('before_model_request')(modelRequest(first.messages));
  // A prepared graph request is single-use, not permission to replay a stale turn.
  await assert.rejects(f.handlers.get('before_model_request')(modelRequest(first.messages)), /blocked/);
  const second = await f.handlers.get('context')({messages: first.messages});
  await assert.rejects(f.handlers.get('before_model_request')(modelRequest(first.messages)), /blocked/);
  const fresh = await f.handlers.get('context')({messages: second.messages});
  await f.handlers.get('before_model_request')(modelRequest(fresh.messages));
  const duplicate = await f.handlers.get('context')({messages: []});
  await assert.rejects(f.handlers.get('before_model_request')(modelRequest([
    ...duplicate.messages, duplicate.messages.at(-1)])), /blocked/);
});

test("prepared graph context does not admit changed research meaning or foreign ownership", async t => {
  const f = await fixture(t, {getControllerState: () => ({graph: {schema: 'capstone-enterprise-graph/2'}})});
  const prepared = await f.handlers.get('context')({messages: []});
  f.view.research_revision = f.view.state.revision = 2;
  f.view.state.goal = 'Different accepted goal';
  await writeFile(join(f.root, 'view.json'), JSON.stringify(f.view));
  await assert.rejects(f.handlers.get('before_model_request')(modelRequest(prepared.messages)), /blocked/);
  const next = await f.handlers.get('context')({messages: []});
  f.view.attempt_id = 'another-attempt';
  await writeFile(join(f.root, 'view.json'), JSON.stringify(f.view));
  await assert.rejects(f.handlers.get('before_model_request')(modelRequest(next.messages)), /blocked/);
});

test("trusted compaction requests remain separate and the agent guard resumes afterwards", async t => {
  const f = await fixture(t);
  assert.equal(typeof f.handlers.get("session_before_compact"), "function");
  await f.handlers.get("session_before_compact")({});
  await f.handlers.get("before_model_request")(modelRequest([{ role: "user", content: "Summarize stored history" }]));
  await f.handlers.get("session_compact_failed")({});
  await assert.rejects(f.handlers.get("before_model_request")(modelRequest([{ role: "user", content: "Continue" }])), /blocked/);
});

test("empty research adds no context message or mandatory research creation", async t => {
  const f = await fixture(t, { state: null });
  const messages = [{ role: "user", content: "Hello" }];
  assert.deepEqual((await f.handlers.get("context")({ messages })).messages, messages);
  await f.handlers.get("before_model_request")(modelRequest(messages));
  assert.deepEqual(await readdir(join(f.root, "requests")), []);
});

test("bounded context marks omitted records instead of silently claiming full coverage", async t => {
  const f = await fixture(t,{runtimeLimits:{research_summary_chars:16384}});
  f.view.state.claims = Array.from({ length: 64 }, (_, i) => ({ claim_id: `claim-${i}`, statement: "x".repeat(2000), status: "pending", refs: [] }));
  f.view.state.notes = Array.from({ length: 64 }, (_, i) => ({ note_id: `note-${i}`, text: "y".repeat(2000), refs: [] }));
  await writeFile(join(f.root, "view.json"), JSON.stringify(f.view));
  const result = await f.handlers.get("context")({ messages: [] });
  assert.ok(Buffer.byteLength(result.messages[0].content) <= 16384);
  assert.match(result.messages[0].content, /omitted/);
});

test("a symlink view is rejected rather than read", async t => {
  const f = await fixture(t);
  const outside = join(f.root, "other.json");
  await writeFile(outside, JSON.stringify(f.view));
  await rm(join(f.root, "view.json"));
  await symlink(outside, join(f.root, "view.json"));
  await assert.rejects(f.handlers.get("context")({ messages: [] }));
});
