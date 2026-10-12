// Actual pinned Pi sessions with an in-memory provider. No network or credentials.
import { access, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import readline from "node:readline";

const [repo, root] = process.argv.slice(2);
const runtimeImport = name => import(pathToFileURL(join(repo, ".grid-agent/runtime/pi/source/packages/coding-agent/dist/core", `${name}.js`)));
const [{ createAgentSession }, { ModelRuntime }, { SettingsManager }, { SessionManager }] = await Promise.all([
  runtimeImport("sdk"), runtimeImport("model-runtime"), runtimeImport("settings-manager"), runtimeImport("session-manager"),
]);
const { createAssistantMessageEventStream } = await import(pathToFileURL(join(repo, "packages/pi-capability-tools/node_modules/@earendil-works/pi-ai/dist/index.js")));
const agentDir = join(root, "agent"), cwd = join(root, "cwd");
await mkdir(join(agentDir, "extensions"), { recursive: true });
await mkdir(cwd, { recursive: true });
const extensionUrl = pathToFileURL(join(repo, "packages/pi-capability-tools/src/domain-tools.mjs")).href;
await writeFile(join(agentDir, "extensions/capabilities.ts"), `export { default } from ${JSON.stringify(extensionUrl)};\n`);
try {
  await access(join(root, "drop-context"));
  await writeFile(join(agentDir, "extensions/zz-drop-context.ts"),
    'export default pi => pi.on("context", event => ({ messages: event.messages.filter(message => message.customType !== "capstone-research-state") }));\n');
} catch (error) { if (error.code !== "ENOENT") throw error; }
const modelRuntime = await ModelRuntime.create({ authPath: join(agentDir, "auth.json"), modelsPath: null, refreshOnCreate: false });
modelRuntime.getAuth = async () => ({ auth: { apiKey: "offline-test-only" } });
modelRuntime.hasConfiguredAuth = () => true;
const model = { id: "research-fixture", name: "Research fixture", api: "anthropic-messages", provider: "offline-fixture",
  baseUrl: "https://not-used.invalid", reasoning: false, input: ["text"],
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 131072, maxTokens: 4096 };
let phase = "agent", modelCalls = 0, agentCalls = 0, promptCount = 0, sessionFile, session;
modelRuntime.streamSimple = (selected, context) => {
  modelCalls += 1;
  const record = { phase, context };
  // The test reads exactly what the actual SDK handed to its provider transport.
  const stream = createAssistantMessageEventStream();
  void (async () => {
    await writeFile(join(root, `request-${String(modelCalls).padStart(3, "0")}.json`), JSON.stringify(record));
    const toolUse = phase === "agent" && ++agentCalls === 1;
    const message = { role: "assistant", api: selected.api, provider: selected.provider, model: selected.id,
      content: toolUse ? [{ type: "toolCall", id: "research-call-1", name: "agent_research_update", arguments: {
        expected_revision: 0, changes: { goal: "Verify persistent research state", open_questions: ["Does recovery retain the current goal?"] },
      } }] : [{ type: "text", text: phase === "compaction" ? "History was compacted. Research is stored separately." : "Research saved." }],
      stopReason: toolUse ? "toolUse" : "stop", timestamp: Date.now(),
      usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    };
    stream.push({ type: "start", partial: message });
    stream.push({ type: "done", reason: message.stopReason, message });
  })().catch(error => stream.end({ role: "assistant", content: [], stopReason: "error", errorMessage: String(error) }));
  return stream;
};
async function start(manager) {
  const result = await createAgentSession({ cwd, agentDir, model, modelRuntime, noTools: "builtin",
    settingsManager: SettingsManager.inMemory({ compaction: { enabled: false, reserveTokens: 128, keepRecentTokens: 1 } }), sessionManager: manager });
  if (result.extensionsResult.errors.length) throw new Error(JSON.stringify(result.extensionsResult.errors));
  session = result.session;
  session.subscribe(event => {
    if (["tool_execution_start", "tool_execution_end"].includes(event.type)) console.log(JSON.stringify(event));
  });
  if (!session.getActiveToolNames().includes("agent_research_update")) throw new Error("research tool missing from actual Pi");
}
await start(SessionManager.create(cwd, join(root, "sessions")));
for await (const line of readline.createInterface({ input: process.stdin })) {
  const request = JSON.parse(line);
  if (request.type !== "prompt") continue;
  promptCount += 1;
  console.log(JSON.stringify({ type: "prompt_ack", ok: true, request_id: request.request_id }));
  if (promptCount === 3) {
    session.dispose();
    await start(SessionManager.open(sessionFile));
  }
  await session.prompt(request.message);
  if (promptCount === 2) {
    phase = "compaction";
    await session.compact();
    phase = "agent";
    await session.prompt("Continue after compaction");
    sessionFile = session.sessionManager.getSessionFile();
    await writeFile(join(root, "compaction.json"), JSON.stringify({
      compacted: session.sessionManager.getEntries().some(entry => entry.type === "compaction"), sessionFile,
    }));
  }
  console.log(JSON.stringify({ type: "agent_end", messages: session.agent.state.messages, request_id: request.request_id }));
}
session.dispose();
