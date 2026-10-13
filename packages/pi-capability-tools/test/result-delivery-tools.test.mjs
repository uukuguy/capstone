import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, realpath, rm, writeFile, readdir, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { configureResultDeliveryTool } from "../src/result-delivery-tools.mjs";

async function setup(t) {
  const root = await realpath(await mkdtemp(join(tmpdir(), "capstone-result-delivery-")));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "requests")); await mkdir(join(root, "receipts"));
  await writeFile(join(root, "binding.json"), JSON.stringify({ schema: "capstone-result-delivery/1", thread_id: "thr_one", attempt_id: "attempt_one" }));
  const tools = new Map();
  configureResultDeliveryTool({ registerTool: tool => tools.set(tool.name, tool) }, root, { timeoutMs: 1000 });
  return { root, tool: tools.get("capstone_result_delivery_read") };
}

test("delivery tool returns host coverage without rows or new evidence", async t => {
  const { root, tool } = await setup(t);
  const response = tool.execute("call", { result_ref: "result:one", execution_purpose: "确认完整结果已准备交付" });
  let names = [];
  while (!names.length) { names = (await readdir(join(root, "requests"))).filter(n => n.endsWith(".json")); await new Promise(r => setTimeout(r, 5)); }
  const bytes = await readFile(join(root, "requests", names[0]), "utf8"), request = JSON.parse(bytes);
  await writeFile(join(root, "receipts", names[0]), JSON.stringify({ schema: "capstone-result-delivery-receipt/1",
    ...request, request_sha256: createHash("sha256").update(bytes).digest("hex"), status: "prepared",
    tables: [{ table_id: "values", total_rows: 39, complete: true }], answer_admission_pending: true }));
  const result = await response;
  assert.equal(result.isError, false);
  assert.equal(result.details.presentation_receipt.tables[0].total_rows, 39);
  assert.deepEqual(result.details.result_refs, []);
  assert.deepEqual(result.details.evidence_refs, []);
});

test("delivery tool rejects caller paths and preserves unavailable outcomes", async t => {
  const { root, tool } = await setup(t);
  assert.equal((await tool.execute("call", { result_ref: "result:one", execution_purpose: "Check", path: "/secret" })).isError, true);
  assert.equal((await readdir(join(root, "requests"))).length, 0);
  const abort = new AbortController(); abort.abort();
  const result = await tool.execute("cancelled", { result_ref: "result:one", execution_purpose: "Check" }, abort.signal);
  assert.equal(result.isError, true);
  assert.equal(result.details.error.code, "result_delivery_unavailable");
});
