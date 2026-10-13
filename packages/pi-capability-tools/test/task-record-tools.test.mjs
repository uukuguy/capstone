import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("selected task tool reads bound records and rejects another source or changed bytes", async t => {
  const root = await realpath(await mkdtemp(join(tmpdir(), "capstone-task-records-")));
  t.after(() => rm(root, { recursive: true, force: true }));
  const page = { schema: "capstone-selected-task-records/1", thread_id: "thr_one", attempt_id: "attempt_old",
    historical_only: true, instruction: "Original question", events: [{ event_type: "tool_completed", payload: { ok: false } }],
    next_after: 4, has_more: false };
  const bytes = JSON.stringify(page);
  await writeFile(join(root, "0.json"), bytes);
  await writeFile(join(root, "manifest.json"), JSON.stringify({ schema: "capstone-selected-task-input/1",
    thread_id: page.thread_id, attempt_id: page.attempt_id,
    pages: [{ after: 0, sha256: createHash("sha256").update(bytes).digest("hex") }] }));
  const tools = new Map();
  const { configureTaskRecordTool } = await import("../src/task-record-tools.mjs");
  configureTaskRecordTool({ registerTool: tool => tools.set(tool.name, tool) }, root);
  const tool = tools.get("agent_task_records_read");
  assert.ok(tool);
  const result = await tool.execute("call-one", { after: 0 });
  assert.equal(result.details.events[0].payload.ok, false);
  assert.equal(result.details.historical_only, true);
  assert.equal((await tool.execute("call-two", { after: 0, attempt_id: "attempt_other" })).isError, true);
  await writeFile(join(root, "0.json"), bytes + " ");
  assert.equal((await tool.execute("call-three", { after: 0 })).isError, true);
});
