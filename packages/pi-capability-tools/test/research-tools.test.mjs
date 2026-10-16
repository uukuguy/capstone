import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, realpath, rename, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

async function fixture(t, { progress = false, state = { research_id: "research-1", revision: 1, goal: "Check the selected model", condition_refs: [], claims: [], notes: [], open_questions: [] } } = {}) {
  const root = await realpath(await mkdtemp(join(tmpdir(), "capability-research-")));
  t.after(() => rm(root, { recursive: true, force: true }));
  const binding = { schema_version: "capability-research-channel/1.0", run_id: "run-1", turn_id: "turn-1", attempt_id: "attempt-1", research_id: "research-1", read_tool_schema: {
    type: "object", additionalProperties: false, properties: { section: { type: "string", enum: ["overview", "claims", "notes", "questions", "receipt"] },
      request_id: { type: "string", pattern: "^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$" },
      offset: { type: "integer", minimum: 0 }, limit: { type: "integer", minimum: 1, maximum: 8 } },
  }, update_tool_schema: {
    type: "object", additionalProperties: false, required: ["expected_revision", "changes"], properties: {
      expected_revision: { type: "integer", minimum: 0 },
      changes: { type: "object", additionalProperties: false, properties: { goal: { type: "string", minLength: 1, maxLength: 4000 } }, minProperties: 1 },
    },
  }, depth_tool_schema: { type: "object", additionalProperties: false, required: ["level"],
    properties: { level: { type: "string", enum: ["off", "high"] } } } };
  const view = { ...binding, schema_version: "capability-research-view/1.0", research_revision: state?.revision ?? 0, state };
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
  configureResearchTools({ registerTool: tool => tools.set(tool.name, tool), on: (name, handler) => handlers.set(name, handler),
    getThinkingLevel: () => thinking, setThinkingLevel: level => { thinking = level; } }, root, {
    timeoutMs: 1000, fatal: message => { failures.push(message); throw new Error("research request blocked"); },
  });
  return { root, binding, view, tools, handlers, failures, thinking: () => thinking };
}

function modelRequest(messages) {
  return { context: { messages: messages.map(message => message.role === "custom"
    ? { role: "user", content: [{ type: "text", text: message.content }] } : message) } };
}

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
  const f = await fixture(t);
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
