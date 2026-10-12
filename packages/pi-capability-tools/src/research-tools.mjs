import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type, validateToolArguments } from "@earendil-works/pi-ai";
import { createHash, randomUUID } from "node:crypto";
import { constants, lstatSync, openSync, closeSync, fstatSync, readFileSync, realpathSync } from "node:fs";
import { link, open, unlink } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { captureFatal } from "./model-request-capture.mjs";

export const RESEARCH_TOOL_NAMES = Object.freeze(["agent_research_read", "agent_research_update", "agent_research_depth"]);
const CUSTOM_TYPE = "capstone-research-state";
const PREFIX = "Committed research state (agent judgments, not Authority facts):\n";
const MAX_FILE_BYTES = 2_097_152;
const MAX_CONTEXT_BYTES = 16_384;
const ID = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
const { O_RDONLY, O_DIRECTORY, O_NOFOLLOW } = constants;

/** Register host-bound research tools and a request-level readiness guard. */
export function configureResearchTools(pi, channelPath, { timeoutMs = 5000, fatal = captureFatal } = {}) {
  if (!isAbsolute(channelPath) || realpathSync(channelPath) !== resolve(channelPath)) {
    throw new Error("research channel must be a real absolute directory");
  }
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 60_000) {
    throw new Error("research wait limit is invalid");
  }
  const root = resolve(channelPath);
  const pinned = new Map([root, join(root, "requests"), join(root, "receipts")].map(path => {
    const stat = lstatSync(path);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error("research channel directory is invalid");
    return [path, `${stat.dev}:${stat.ino}`];
  }));
  function verifyDirectories() {
    for (const [path, identity] of pinned) {
      const stat = lstatSync(path);
      if (!stat.isDirectory() || stat.isSymbolicLink() || `${stat.dev}:${stat.ino}` !== identity || realpathSync(path) !== path) {
        throw new Error("research channel directory changed");
      }
    }
  }
  function readBytes(path) {
    verifyDirectories();
    const fd = openSync(path, O_RDONLY | O_NOFOLLOW);
    try {
      const before = fstatSync(fd, { bigint: true });
      if (!before.isFile() || before.size > BigInt(MAX_FILE_BYTES)) throw new Error("research file is invalid or too large");
      const data = readFileSync(fd);
      const after = fstatSync(fd, { bigint: true }), named = lstatSync(path, { bigint: true });
      const identity = stat => [stat.dev, stat.ino, stat.size, stat.mtimeNs, stat.ctimeNs].join(":");
      if (data.length > MAX_FILE_BYTES || identity(before) !== identity(after) || identity(after) !== identity(named)) {
        throw new Error("research file changed while reading");
      }
      verifyDirectories();
      return data;
    } finally { closeSync(fd); }
  }
  const readJson = path => JSON.parse(readBytes(path).toString("utf8"));
  const binding = readJson(join(root, "binding.json"));
  if (binding.schema_version !== "capability-research-channel/1.0"
      || ![binding.run_id, binding.turn_id, binding.attempt_id, binding.research_id].every(value => typeof value === "string" && ID.test(value))
      || binding.update_tool_schema?.additionalProperties !== false
      || binding.read_tool_schema?.additionalProperties !== false
      || Object.keys(binding.update_tool_schema?.properties ?? {}).sort().join(",") !== "changes,expected_revision") {
    throw new Error("research channel binding is invalid");
  }
  let observedRevision = 0, observedHash, requiredRevision = 0, compacting = false;
  function loadView() {
    const view = readJson(join(root, "view.json"));
    if (view.schema_version !== "capability-research-view/1.0"
        || ["run_id", "turn_id", "attempt_id", "research_id"].some(key => view[key] !== binding[key])
        || !Number.isInteger(view.research_revision) || view.research_revision < requiredRevision
        || view.research_revision < observedRevision
        || (view.state === null ? view.research_revision !== 0
          : view.state?.research_id !== binding.research_id || view.state?.revision !== view.research_revision)) {
      throw new Error("research view identity or revision is invalid");
    }
    const hash = digest(JSON.stringify(sortJson(view)));
    if (observedHash && view.research_revision === observedRevision && hash !== observedHash) {
      throw new Error("research content changed without a committed revision");
    }
    observedRevision = view.research_revision;
    observedHash = hash;
    return view;
  }
  function summary(view) {
    if (!view.state) return { ...identity(view), state: null };
    const state = view.state;
    const projected = {
      ...identity(view), goal: state.goal.slice(0, 1024),
      condition_refs: (state.condition_refs ?? []).slice(0, 8),
      claims: (state.claims ?? []).slice(0, 8).map(item => ({ ...item, statement: item.statement.slice(0, 240), refs: item.refs.slice(0, 2) })),
      notes: (state.notes ?? []).slice(-4).map(item => ({ note_id: item.note_id, text: item.text.slice(0, 160) })),
      open_questions: (state.open_questions ?? []).slice(0, 8).map(text => text.slice(0, 240)),
      coverage: {},
    };
    const coverage = () => {
      projected.coverage = {
        claims_total: (state.claims ?? []).length, notes_total: (state.notes ?? []).length,
        questions_total: (state.open_questions ?? []).length, conditions_total: (state.condition_refs ?? []).length,
        omitted: { claims: (state.claims ?? []).length - projected.claims.length,
          notes: (state.notes ?? []).length - projected.notes.length,
          questions: (state.open_questions ?? []).length - projected.open_questions.length,
          conditions: (state.condition_refs ?? []).length - projected.condition_refs.length },
        text_may_be_truncated: true,
      };
    };
    coverage();
    for (const field of ["notes", "claims", "open_questions", "condition_refs"]) {
      while (projected[field].length && Buffer.byteLength(PREFIX + JSON.stringify(projected)) > MAX_CONTEXT_BYTES) {
        projected[field].pop(); coverage();
      }
    }
    if (Buffer.byteLength(PREFIX + JSON.stringify(projected)) > MAX_CONTEXT_BYTES) throw new Error("research summary exceeds context limit");
    return projected;
  }
  const readParameters = Type.Unsafe(binding.read_tool_schema);
  const updateParameters = Type.Unsafe(binding.update_tool_schema);
  function verifyReceipt(ack, requestId, hash, expectedRevision) {
    if (ack.schema_version !== "capability-research-receipt/1.0" || ack.request_id !== requestId
        || ack.request_sha256 !== hash
        || ["run_id", "turn_id", "attempt_id"].some(key => ack[key] !== binding[key])
        || !["committed", "rejected", "not_confirmed"].includes(ack.status)) return false;
    if (ack.status !== "committed") return true;
    return ack.receipt?.research_id === binding.research_id && ack.receipt?.request_id === requestId
      && ack.receipt?.research_revision === expectedRevision + 1
      && Number.isInteger(ack.receipt?.event_sequence) && ack.receipt.event_sequence >= 1;
  }
  pi.registerTool(defineTool({
    name: RESEARCH_TOOL_NAMES[0], label: "Read research state",
    description: "Read committed research state only when needed. Overview is bounded; page claims, notes or questions for full text. This does not retrieve Authority results or create evidence.",
    parameters: readParameters,
    async execute(id, params) {
      try {
        const input = validate(readParameters, RESEARCH_TOOL_NAMES[0], id, params);
        const section = input.section ?? "overview";
        if (section === "receipt") {
          if (typeof input.request_id !== "string" || !ID.test(input.request_id)) return failure(RESEARCH_TOOL_NAMES[0], "invalid_arguments");
          const raw = readBytes(join(root, "requests", input.request_id + ".json"));
          const request = JSON.parse(raw.toString("utf8"));
          if (request.request_id !== input.request_id) return failure(RESEARCH_TOOL_NAMES[0], "research_receipt_mismatch");
          let ack;
          try { ack = readJson(join(root, "receipts", input.request_id + ".json")); }
          catch (error) {
            if (error?.code === "ENOENT") return success(RESEARCH_TOOL_NAMES[0], { status: "not_confirmed", request_id: input.request_id });
            throw error;
          }
          if (!verifyReceipt(ack, input.request_id, digest(raw), request.expected_revision)) return failure(RESEARCH_TOOL_NAMES[0], "research_receipt_mismatch");
          if (ack.status === "committed") requiredRevision = Math.max(requiredRevision, ack.receipt.research_revision);
          return success(RESEARCH_TOOL_NAMES[0], ack);
        }
        if (input.request_id !== undefined) return failure(RESEARCH_TOOL_NAMES[0], "invalid_arguments");
        const view = loadView();
        if (section === "overview") return success(RESEARCH_TOOL_NAMES[0], summary(view));
        const records = view.state?.[section === "questions" ? "open_questions" : section] ?? [];
        const offset = input.offset ?? 0, limit = input.limit ?? 8;
        return success(RESEARCH_TOOL_NAMES[0], { ...identity(view), section, total: records.length, offset,
          next_offset: offset + limit < records.length ? offset + limit : null, records: records.slice(offset, offset + limit) });
      } catch { return failure(RESEARCH_TOOL_NAMES[0], "research_read_failed"); }
    },
  }));
  pi.registerTool(defineTool({
    name: RESEARCH_TOOL_NAMES[1], label: "Update research state",
    description: "Commit meaningful research changes using the last read revision. Wait for the host receipt. Rejection is not success; an unconfirmed outcome needs receipt lookup with the same request identity. Raw observations are already logged; do not update after every tool.",
    parameters: updateParameters,
    async execute(id, params, signal) {
      let input;
      try { input = validate(updateParameters, RESEARCH_TOOL_NAMES[1], id, params); }
      catch { return failure(RESEARCH_TOOL_NAMES[1], "invalid_arguments"); }
      if (typeof id !== "string" || !id || signal?.aborted) return failure(RESEARCH_TOOL_NAMES[1], "research_update_cancelled", { status: "rejected" });
      const requestId = "request-" + digest(id);
      const raw = JSON.stringify({ request_id: requestId, ...input }) + "\n";
      if (Buffer.byteLength(raw) > 1_048_576) return failure(RESEARCH_TOOL_NAMES[1], "research_request_too_large");
      const requestHash = digest(raw), path = join(root, "requests", requestId + ".json");
      try { await publish(path, raw); }
      catch { return failure(RESEARCH_TOOL_NAMES[1], "research_publication_not_confirmed", { status: "not_confirmed", request_id: requestId }); }
      const deadline = Date.now() + timeoutMs;
      while (!signal?.aborted && Date.now() < deadline) {
        try {
          const ack = readJson(join(root, "receipts", requestId + ".json"));
          if (!verifyReceipt(ack, requestId, requestHash, input.expected_revision)) {
            return failure(RESEARCH_TOOL_NAMES[1], "research_receipt_mismatch");
          }
          if (ack.status !== "committed") return failure(RESEARCH_TOOL_NAMES[1], ack.code ?? "research_update_not_confirmed", ack);
          requiredRevision = Math.max(requiredRevision, ack.receipt.research_revision);
          try { loadView(); }
          catch { return failure(RESEARCH_TOOL_NAMES[1], "research_view_not_ready", { ...ack, view_ready: false }); }
          return success(RESEARCH_TOOL_NAMES[1], ack);
        } catch (error) {
          if (error?.code !== "ENOENT") return failure(RESEARCH_TOOL_NAMES[1], "research_receipt_unreadable", { status: "not_confirmed", request_id: requestId });
        }
        await delay(20);
      }
      return failure(RESEARCH_TOOL_NAMES[1], "research_outcome_not_confirmed", { status: "not_confirmed", request_id: requestId });
    },
  }));
  const depthParameters = Type.Unsafe(binding.depth_tool_schema ?? {
    type: "object", additionalProperties: false, properties: {},
  });
  pi.registerTool(defineTool({
    name: RESEARCH_TOOL_NAMES[2], label: "Adjust reasoning depth",
    description: "Adjust reasoning depth for subsequent model steps. Use off for direct work and high for difficult reasoning. This changes no provider, model or Authority state and creates no evidence.",
    parameters: depthParameters,
    async execute(id, params, signal) {
      try {
        const input = validate(depthParameters, RESEARCH_TOOL_NAMES[2], id, params);
        if (!binding.depth_tool_schema || !["off", "high"].includes(input.level)) {
          return failure(RESEARCH_TOOL_NAMES[2], "invalid_arguments");
        }
        if (signal?.aborted) return failure(RESEARCH_TOOL_NAMES[2], "cancelled");
        loadView();
        if (typeof pi.getThinkingLevel !== "function" || typeof pi.setThinkingLevel !== "function") {
          return failure(RESEARCH_TOOL_NAMES[2], "reasoning_control_unavailable");
        }
        const previous = pi.getThinkingLevel();
        pi.setThinkingLevel(input.level);
        return success(RESEARCH_TOOL_NAMES[2], { previous_level: previous,
          requested_level: input.level, applied_level: pi.getThinkingLevel() });
      } catch { return failure(RESEARCH_TOOL_NAMES[2], "reasoning_control_failed"); }
    },
  }));
  pi.on("context", async event => {
    const view = loadView();
    const messages = event.messages.filter(message => !(message.role === "custom" && message.customType === CUSTOM_TYPE));
    if (view.state !== null) messages.push({ role: "custom", customType: CUSTOM_TYPE,
      content: PREFIX + JSON.stringify(summary(view)), display: false, timestamp: 0 });
    return { messages };
  });
  pi.on("before_model_request", async event => {
    // Pi runs its summary request outside transformContext during compaction.
    // This phase is set by trusted lifecycle events, never by prompt text.
    if (compacting) return;
    try {
      const view = loadView();
      if (view.state === null) return;
      const expected = PREFIX + JSON.stringify(summary(view));
      const count = event.context.messages.filter(message => message.role === "user" &&
        (typeof message.content === "string" ? message.content === expected
          : message.content?.some(part => part.type === "text" && part.text === expected))).length;
      if (count !== 1) throw new Error("current research state is absent or duplicated in the model request");
    } catch { return fatal("research context is not ready for the model request"); }
  });
  pi.on("session_before_compact", () => { compacting = true; });
  pi.on("session_compact", () => { compacting = false; });
  pi.on("session_compact_failed", () => { compacting = false; });

  async function publish(path, raw) {
    verifyDirectories();
    const temporary = join(root, "requests", "." + randomUUID() + ".tmp");
    const handle = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | O_NOFOLLOW, 0o600);
    try {
      await handle.writeFile(raw); await handle.sync(); await handle.close();
      verifyDirectories();
      try { await link(temporary, path); }
      catch (error) {
        if (error?.code !== "EEXIST" || JSON.stringify(readJson(path)) !== JSON.stringify(JSON.parse(raw))) throw error;
      }
      const directory = await open(join(root, "requests"), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
      try { await directory.sync(); } finally { await directory.close(); }
      verifyDirectories();
    } finally { await handle.close().catch(() => {}); await unlink(temporary).catch(() => {}); }
  }
}

function identity(view) {
  return Object.fromEntries(["run_id", "turn_id", "attempt_id", "research_id", "research_revision"].map(key => [key, view[key]]));
}
function digest(value) { return createHash("sha256").update(value).digest("hex"); }
function sortJson(value) {
  if (Array.isArray(value)) return value.map(sortJson);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(key => [key, sortJson(value[key])]));
  return value;
}
function validate(parameters, name, id, args) {
  return validateToolArguments({ name, parameters }, { type: "toolCall", id, name, arguments: args });
}
function success(capability, result) {
  return { content: [{ type: "text", text: JSON.stringify(result) }],
    details: { event: "tool_result", capability, ok: true, result, evidence_refs: [] } };
}
function failure(capability, code, result) {
  const errors = Array.isArray(result?.validation_errors) ? result.validation_errors.slice(0, 8) : [];
  const validation = errors.filter(item => typeof item?.message === "string").map(item =>
    `${Array.isArray(item.path) ? item.path.join(".") : "request"}: ${item.message}`).join("; ");
  const message = (typeof result?.message === "string" ? result.message : validation ||
    (result?.status === "not_confirmed" ? "Commit outcome is not confirmed. Read the receipt for the same request_id before writing again."
      : "Research action did not complete. Check the error code and correct the rejected request.")).slice(0, 512);
  const phase = result?.status === "not_confirmed" ? "persist" : "validate";
  return { isError: true, content: [{ type: "text", text: JSON.stringify({ code, phase, message, ...(result ? { result } : {}) }) }],
    details: { event: "tool_result", capability, ok: false, error: { code, phase, message }, ...(result ? { result } : {}), evidence_refs: [] } };
}
