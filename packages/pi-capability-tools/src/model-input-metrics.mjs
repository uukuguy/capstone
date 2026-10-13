import { constants, openSync, closeSync, fstatSync, writeSync, lstatSync, realpathSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";

const size = value => {
  const text = typeof value === "string" ? value : JSON.stringify(value ?? null);
  return { chars: text.length, utf8_bytes: Buffer.byteLength(text) };
};
const toolInput = tool => ({ name: tool.name, description: tool.description, parameters: tool.parameters });
const messageInput = message => ({ role: message.role, content: message.content,
  ...(message.role === "toolResult" ? { toolCallId: message.toolCallId, toolName: message.toolName, isError: message.isError } : {}) });

/** Observe semantic input sizes and native stream timing. Never change model input. */
export function configureModelInputMetrics(pi, record, clock = () => performance.now()) {
  let request = 0, started, firstStream = false;
  pi.on("before_model_request", event => {
    started = clock(); firstStream = false; request += 1;
    const context = event.context ?? {}, tools = (context.tools ?? []).map(toolInput);
    const messages = (context.messages ?? []).map(messageInput), roles = {}, toolResults = [];
    for (const message of messages) {
      const role = ["user", "assistant", "toolResult", "custom"].includes(message.role) ? message.role : "other";
      roles[role] ??= { count: 0, chars: 0, utf8_bytes: 0 };
      const measured = size(message);
      roles[role].count += 1; roles[role].chars += measured.chars; roles[role].utf8_bytes += measured.utf8_bytes;
      if (role === "toolResult") toolResults.push({ name: /^[a-z][a-z0-9_]{0,127}$/.test(message.toolName) ? message.toolName : "other", ...measured });
    }
    record({ schema: "capstone-model-input-metrics/1", kind: "request", request_index: request,
      system: size(context.systemPrompt ?? ""), messages: { count: messages.length, ...size(messages) },
      messages_by_role: roles, tool_results: toolResults,
      tools: { count: tools.length, ...size(tools),
        description_chars: tools.reduce((total, tool) => total + size(tool.description ?? "").chars, 0),
        schema_chars: tools.reduce((total, tool) => total + size(tool.parameters ?? {}).chars, 0) },
      semantic_input: size({ systemPrompt: context.systemPrompt ?? "", tools, messages }) });
    return undefined;
  });
  pi.on("message_update", event => {
    if (started === undefined || firstStream || !["text_delta", "thinking_delta", "toolcall_delta"].includes(event.assistantMessageEvent?.type)) return;
    firstStream = true;
    record({ kind: "first_stream", request_index: request, elapsed_ms: Math.round(clock() - started) });
  });
  pi.on("message_end", event => {
    if (started === undefined || event.message?.role !== "assistant") return;
    const usage = {};
    for (const key of ["input", "output", "cacheRead", "cacheWrite", "totalTokens"])
      if (Number.isSafeInteger(event.message.usage?.[key]) && event.message.usage[key] >= 0) usage[key] = event.message.usage[key];
    record({ kind: "response_end", request_index: request, elapsed_ms: Math.round(clock() - started), usage });
    started = undefined;
  });
}

export default function modelInputMetrics(pi) {
  const directory = process.env.CAPSTONE_MODEL_INPUT_METRICS;
  if (!directory) return;
  if (!isAbsolute(directory) || realpathSync(directory) !== resolve(directory)) throw new Error("model metrics directory is invalid");
  const root = resolve(directory), pinned = lstatSync(root);
  if (!pinned.isDirectory() || pinned.isSymbolicLink()) throw new Error("model metrics directory is invalid");
  configureModelInputMetrics(pi, record => {
    let fd;
    try {
      const current = lstatSync(root);
      if (current.dev !== pinned.dev || current.ino !== pinned.ino || current.isSymbolicLink()) throw new Error("model metrics directory changed");
      fd = openSync(join(root, "input-metrics.jsonl"), constants.O_WRONLY | constants.O_CREAT | constants.O_APPEND | constants.O_NOFOLLOW, 0o600);
      if (!fstatSync(fd).isFile()) throw new Error("model metrics file is invalid");
      const bytes = Buffer.from(JSON.stringify(record) + "\n");
      let offset = 0;
      while (offset < bytes.length) offset += writeSync(fd, bytes, offset, bytes.length - offset);
    } catch {
      // Diagnostics cannot replace or interrupt the formal answer path.
      writeSync(process.stderr.fd, "Model input metrics unavailable.\n");
    } finally { if (fd !== undefined) closeSync(fd); }
  });
}
