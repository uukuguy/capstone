import test from "node:test";
import assert from "node:assert/strict";
import { access, mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { configureModelRequestCapture } from "../src/model-request-capture.mjs";

test("captures the canonical request from before_model_request without provider payloads", async () => {
  const root = await fixtureRoot();
  const handlers = new Map();
  configureModelRequestCapture(
    { on: (name, handler) => handlers.set(name, handler) },
    fixturePaths(root),
  );

  assert.equal(handlers.has("before_model_request"), true);
  assert.equal(handlers.has("before_provider_request"), false);
  await handlers.get("before_model_request")(requestEvent());

  const serialized = await readFile(join(root, "requests/turn-1-r001/input.json"), "utf8");
  const request = JSON.parse(serialized);
  assert.equal(serialized.endsWith("\n"), true);
  assert.equal(request.schema_version, "capability-model-request-input/1.0");
  assert.equal(request.request_id, "turn-1-r001");
  assert.deepEqual(request.source_event_sequences, [1]);
  assert.deepEqual(request.semantic_request.context.messages, [
    { role: "user", content: [{ type: "text", text: "List assets" }] },
  ]);
  assert.equal("provider_payload" in request, false);
});

test("refuses to replace an existing request path", async () => {
  const root = await fixtureRoot();
  await mkdir(join(root, "requests/turn-1-r001"), { recursive: true });
  await writeFile(join(root, "requests/turn-1-r001/input.json"), "original\n", "utf8");
  const failures = [];
  const handlers = new Map();
  configureModelRequestCapture(
    { on: (name, handler) => handlers.set(name, handler) },
    fixturePaths(root),
    (message) => {
      failures.push(message);
      throw new Error("fatal");
    },
  );
  await assert.rejects(handlers.get("before_model_request")(requestEvent()), /fatal/);
  assert.match(failures[0], /request path already exists/);
});

async function fixtureRoot() {
  const root = await mkdtemp(join(tmpdir(), "capability-pi-capture-"));
  await mkdir(join(root, "requests"), { recursive: true });
  await mkdir(join(root, "context"), { recursive: true });
  await writeFile(join(root, "active-turn.json"), JSON.stringify({ turn_id: "turn-1" }), "utf8");
  await writeFile(
    join(root, "capture-state.json"),
    JSON.stringify({
      source_event_sequences: [1],
      context_revision: 3,
      context_state_hash: "a".repeat(64),
    }),
    "utf8",
  );
  return root;
}

function fixturePaths(root) {
  return {
    requestsPath: join(root, "requests"),
    activeTurnPath: join(root, "active-turn.json"),
    captureStatePath: join(root, "capture-state.json"),
    allowedRefsPath: join(root, "context/allowed-refs.json"),
    acknowledgementsPath: join(root, "acks"),
  };
}

function requestEvent() {
  return {
    type: "before_model_request",
    model: { provider: "inventory", api: "messages", id: "inventory-model" },
    context: {
      systemPrompt: "You are an inventory analyst.",
      messages: [{ role: "user", content: "List assets" }],
      tools: [],
    },
    options: {},
  };
}
