import test from "node:test";
import assert from "node:assert/strict";
import { configureModelInputMetrics } from "../src/model-input-metrics.mjs";

test("input diagnostics measure actual request components without changing messages or exposing content", async () => {
  const handlers = new Map(), records = [];
  let now = 100;
  configureModelInputMetrics({ on: (name, handler) => handlers.set(name, handler) },
    record => records.push(record), () => now);
  const event = { context: { systemPrompt: "private-system-text",
    tools: [{ name: "domain_query", description: "private-tool-description", parameters: { type: "object" } }],
    messages: [{ role: "user", content: [{ type: "text", text: "private-user-data" }] },
      { role: "toolResult", toolName: "domain_query", content: [{ type: "text", text: "private-result-data" }] }] } };
  const original = structuredClone(event);
  assert.equal(await handlers.get("before_model_request")(event), undefined);
  assert.deepEqual(event, original);
  assert.equal(records[0].tools.count, 1);
  assert.equal(records[0].messages_by_role.toolResult.count, 1);
  assert.equal(records[0].system.chars, event.context.systemPrompt.length);
  assert.equal(JSON.stringify(records).includes("private-"), false);
  now = 180;
  handlers.get("message_update")({ assistantMessageEvent: { type: "text_delta", delta: "private-stream" } });
  now = 210;
  handlers.get("message_update")({ assistantMessageEvent: { type: "text_delta", delta: "private-second" } });
  assert.equal(records.filter(record => record.kind === "first_stream").length, 1);
  assert.equal(records[1].elapsed_ms, 80);
  now = 500;
  handlers.get("message_end")({ message: { role: "assistant", usage: { input: 12, output: 5, cacheRead: 10, totalTokens: 27, cost: { total: 100 } } } });
  assert.equal(records[2].elapsed_ms, 400);
  assert.equal(records[2].usage.input, 12);
  assert.equal("cost" in records[2].usage, false);
});
