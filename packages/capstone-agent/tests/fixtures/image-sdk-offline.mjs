// Model decisions are scripted; the pinned SDK performs actual image reads.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {pathToFileURL} from "node:url";
import {resolve, dirname} from "node:path";
const config = JSON.parse(readFileSync(process.argv[2], "utf8"));
const sdk = await import(pathToFileURL(config.sdk).href);
const ai = await import(pathToFileURL(resolve(dirname(config.sdk), "../../ai/dist/index.js")).href);
const {runManagedSession} = await import(pathToFileURL(process.argv[3]).href);
const model = {id: config.model, name: "Offline image read", provider: "capstone-general",
  api: "openai-completions", baseUrl: "http://127.0.0.1:1", reasoning: false,
  input: ["text", "image"], contextWindow: 32000, maxTokens: 1024,
  cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}};
let round = 0;
const runtime = {getModel: () => model, hasConfiguredAuth: () => true,
  getAuth: async () => ({auth: {apiKey: "offline-fixture"}}), isUsingOAuth: () => false,
  streamSimple(_model, context) {
    let content;
    if (round++ === 0) {
      content = [1, 2].map(i => ({type: "toolCall", id: "image-" + i, name: "read", arguments: {path: "chart.png"}}));
    } else {
      const results = context.messages.filter(item => item.role === "toolResult");
      assert.equal(results.length, 2);
      for (const result of results) {
        const image = result.content.find(part => part.type === "image");
        assert.ok(image.data.length > 262144, "the model retains the large image");
      }
      content = [{type: "text", text: "Both original images were available to the model."}];
    }
    const message = {role: "assistant", content, api: model.api, provider: model.provider,
      model: model.id, timestamp: Date.now(), usage: {input: 0, output: 0, cacheRead: 0,
        cacheWrite: 0, totalTokens: 0, cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0}},
      stopReason: content.some(part => part.type === "toolCall") ? "toolUse" : "stop"};
    const stream = ai.createAssistantMessageEventStream();
    stream.push({type: "done", reason: message.stopReason, message}); stream.end(); return stream;
  }};
await runManagedSession(config, sdk, runtime);
assert.equal(round, 2);
