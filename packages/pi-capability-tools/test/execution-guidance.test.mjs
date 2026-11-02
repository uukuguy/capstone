import test from "node:test";
import assert from "node:assert/strict";
import { configureExecutionGuidance } from "../src/execution-guidance.mjs";

test("shared execution guidance extends policy without adding tools or calls", async () => {
  const handlers = new Map();
  configureExecutionGuidance({ on: (name, handler) => handlers.set(name, handler) });
  assert.deepEqual([...handlers.keys()], ["before_agent_start"]);
  const result = await handlers.get("before_agent_start")({systemPrompt: "Application and domain policy."});
  assert.ok(result.systemPrompt.startsWith("Application and domain policy.\n\n"));
  assert.match(result.systemPrompt, /independent.*same model response/s);
  assert.match(result.systemPrompt, /dependent actions.*in order/s);
  assert.match(result.systemPrompt, /does not grant tools or access/);
  assert.doesNotMatch(result.systemPrompt, /pandas|report\.html|price|research_read/);
});

test("capability notice follows the current model input rather than guessed image access", async () => {
  const handlers = new Map();
  configureExecutionGuidance({ on: (name, handler) => handlers.set(name, handler) });
  const start = handlers.get("before_agent_start");
  const text = await start({systemPrompt: "Policy."}, {model: {input: ["text"]}});
  assert.match(text.systemPrompt, /current model cannot inspect image content/i);
  assert.match(text.systemPrompt, /pixel statistics.*semantic/i);
  const vision = await start({systemPrompt: "Policy."}, {model: {input: ["text", "image"]}});
  assert.doesNotMatch(vision.systemPrompt, /current model cannot inspect image content/i);
  const unknown = await start({systemPrompt: "Policy."}, {});
  assert.doesNotMatch(unknown.systemPrompt, /current model cannot inspect image content/i);
});
