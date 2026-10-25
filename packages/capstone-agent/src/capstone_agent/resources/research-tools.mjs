import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type, validateToolArguments } from "@earendil-works/pi-ai";
import { createHash, randomUUID } from "node:crypto";
import { constants, lstatSync, openSync, closeSync, fstatSync, readFileSync, realpathSync } from "node:fs";
import { link, open, unlink } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { captureFatal } from "./model-request-capture.mjs";
import { runtimeLimits as resolveLimits, checkCapacity,sameRuntimeLimits,runtimeLimitMode as resolvedMode } from './runtime-limits.mjs';
import {windowResearchContext} from './research-context-window.mjs';

export const RESEARCH_TOOL_NAMES = Object.freeze(["agent_research_read", "agent_research_update", "agent_research_depth", "agent_task_progress"]);
const CUSTOM_TYPE = "capstone-research-state";
const PREFIX = "Committed research state (agent judgments, not Authority facts):\n";
const ID = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
const { O_RDONLY, O_DIRECTORY, O_NOFOLLOW } = constants;

/** Register host-bound research tools and a request-level readiness guard. */
export function configureResearchTools(pi, channelPath, { timeoutMs, fatal = captureFatal, runtimeLimits, runtimeLimitMode: limitMode, getControllerState, isRecordVisible, boundedGraphContext=false, retainedWorkBackground=false } = {}) {
  const registered = new Map();
  const register = definition => {
    registered.set(definition.name, definition);
    pi.registerTool(definition);
  };
  let limits=resolveLimits(runtimeLimits,{mode:limitMode});
  // Pi derives execution errors from exceptions, not result.isError. Use its
  // result hook so rejected research operations retain their structured receipt
  // and are marked failed in both model context and execution events.
  pi.on("tool_result", event => {
    if (RESEARCH_TOOL_NAMES.includes(event.toolName) && event.details?.ok === false) {
      return { isError: true };
    }
  });
  if (!isAbsolute(channelPath) || realpathSync(channelPath) !== resolve(channelPath)) {
    throw new Error("research channel must be a real absolute directory");
  }
  const waitMs=timeoutMs ?? limits.tool_timeout_seconds * 1000;
  if (!Number.isSafeInteger(waitMs) || waitMs < 1 || waitMs > 2147483647) {
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
      if (!before.isFile()) throw new Error('research file is invalid');
      checkCapacity(limits,'research_response_bytes',Number(before.size),'bytes','research_read');
      const data = readFileSync(fd);
      const after = fstatSync(fd, { bigint: true }), named = lstatSync(path, { bigint: true });
      const identity = stat => [stat.dev, stat.ino, stat.size, stat.mtimeNs, stat.ctimeNs].join(":");
      checkCapacity(limits,'research_response_bytes',data.length,'bytes','research_read');
      if (identity(before) !== identity(after) || identity(after) !== identity(named)) {
        throw new Error("research file changed while reading");
      }
      verifyDirectories();
      return data;
    } finally { closeSync(fd); }
  }
  const readJson = path => JSON.parse(readBytes(path).toString("utf8"));
  const binding = readJson(join(root, "binding.json"));
  if(binding.runtime_limits !== undefined && runtimeLimits !== undefined && !sameRuntimeLimits(binding.runtime_limits,runtimeLimits)) {
    throw new Error('research binding runtime_limits differ from initialized tool limits');
  }
  limits=resolveLimits({...binding.runtime_limits,...runtimeLimits},{mode:limitMode??binding.runtime_limit_mode});
  if (binding.schema_version !== "capability-research-channel/1.0"
      || ![binding.run_id, binding.turn_id, binding.attempt_id, binding.research_id].every(value => typeof value === "string" && ID.test(value))
      || binding.update_tool_schema?.additionalProperties !== false
      || binding.read_tool_schema?.additionalProperties !== false
      || Object.keys(binding.update_tool_schema?.properties ?? {}).sort().join(",") !== "changes,expected_revision") {
    throw new Error("research channel binding is invalid");
  }
  let observedRevision = 0, observedHash, requiredRevision = 0, compacting = false;
  let preparedGraphRequest = null;
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
  const visibleNotes = state => (state.notes ?? []).filter(item =>
    !['runtime.checkpoint.', 'runtime.dispatch.'].some(prefix => item.note_id.startsWith(prefix)));
  const researchMeaning = view => digest(JSON.stringify(sortJson({
    goal: view.state.goal, condition_refs: view.state.condition_refs ?? [], claims: view.state.claims ?? [],
    notes: visibleNotes(view.state), open_questions: view.state.open_questions ?? [],
  })));
  async function summary(view, {fullCycle=false, captureGraph,offset=0,pageSize=8}={}) {
    const stateScope={kind:'research_bookkeeping',turn_id:binding.turn_id,attempt_id:binding.attempt_id,
      research_id:binding.research_id,live_environment_observation:false};
    if (!view.state) return { ...identity(view), state_scope:stateScope, state: null };
    const state = view.state;
    const debug=resolvedMode(limits)==='debug';
    const cycle=getControllerState?structuredClone(await getControllerState({full:fullCycle})):undefined;
    captureGraph?.(cycle?.graph?.schema === 'capstone-enterprise-graph/2');
    const projected = {
      ...identity(view), goal: debug?state.goal:state.goal.slice(0,Math.floor(limits.research_summary_chars/4)),
      state_scope:stateScope,
      ...(retainedWorkBackground?{goal_scope:'retained_work_background',
        scope_notice:'The retained Work goal and unresolved historical items are background. The current user instruction controls this turn and is fresh authorization even when its text repeats a terminal request. The cycle below describes only this attempt research controller, not operating-system processes, other attempts or live external systems. An idle or empty research cycle cannot establish that no processes or tasks are active elsewhere.'}:{}),
      ...(cycle?{cycle}:{}),
      condition_refs: [...(state.condition_refs ?? [])],
      claims: (state.claims ?? []).map(item => ({ ...item, statement: debug?item.statement:item.statement.slice(0,limits.research_text_chars), refs:[...item.refs] })),
      notes: visibleNotes(state)
        .map(item => ({ note_id:item.note_id,text:debug?item.text:item.text.slice(0,limits.research_text_chars) })),
      open_questions: (state.open_questions ?? []).map(text=>debug?text:text.slice(0,limits.research_text_chars)),
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
    if(boundedGraphContext&&cycle?.graph?.schema==='capstone-enterprise-graph/2'){
      return windowResearchContext(projected,{limit:limits.research_summary_chars-Array.from(PREFIX).length,offset,pageSize});
    }
    let size=Array.from(PREFIX+JSON.stringify(projected)).length;
    if(debug&&!fullCycle)checkCapacity(limits,'research_summary_chars',size,'characters','research_summary');
    for (const field of ["notes", "claims", "open_questions", "condition_refs"]) {
      while (projected[field].length && size > limits.research_summary_chars) {
        size-=Array.from(JSON.stringify(projected[field].pop())).length+1;
      }
      coverage();
      size=Array.from(PREFIX+JSON.stringify(projected)).length;
    }
    if(cycle&&size>limits.research_summary_chars){
      const action=cycle.pending_action;
      const chars=value=>typeof value==='string'?Array.from(value).length:0;
      projected.cycle={phase:cycle.phase,round:cycle.round,
        pending_action:action?Object.fromEntries(['id','kind','objective_id','attempt_id','round'].filter(key=>Object.hasOwn(action,key)).map(key=>[key,action[key]])):null,
        checkpoint:cycle.checkpoint,update_pending:cycle.update_pending,
        coverage:{complete:false,omitted:{purpose_chars:chars(action?.purpose),questions:action?.questions?.length??0,
          question_chars:(action?.questions??[]).reduce((n,text)=>n+chars(text),0),
          expected_outputs:action?.expected_outputs?.length??0,checks:action?.checks?.length??0,
          derived_from:action?.derived_from?.length??0,next_action_chars:chars(cycle.next_action)},
          recovery:'Read agent_research_read section="overview" for the complete current cycle and exact accepted questions. This compact identity omits action text; do not infer delegation questions.'}};
    }
    checkCapacity(limits,'research_summary_chars',Array.from(PREFIX+JSON.stringify(projected)).length,'characters','research_summary');
    if(fullCycle&&cycle)projected.cycle=cycle;
    return projected;
  }
  const readParameters = Type.Unsafe(binding.read_tool_schema);
  const updateParameters = Type.Unsafe(binding.update_tool_schema);
  if (binding.progress_tool_schema?.additionalProperties === false) {
    const progressParameters = Type.Unsafe(binding.progress_tool_schema);
    register(defineTool({
      name: "agent_task_progress", label: "Record task progress",
      description: "Record meaningful work objectives, observations, changed methods or limitations alongside useful actions. A tool call or model turn is not a task step. When tracking an objective, pair a stable step_id with phase started, updated or completed and reuse it across related calls. Do not add progress-only model rounds. Use the user's language and actual receipt references. This is a public work record, not independent verification or private reasoning.",
      parameters: progressParameters,
      async execute(id, params, signal) {
        try {
          const record = validate(progressParameters, "agent_task_progress", id, params);
          checkCapacity(limits,'research_progress_chars',Array.from(record.text).length,'characters','research_progress');
          if(record.purpose)checkCapacity(limits,'research_progress_chars',Array.from(record.purpose).length,'characters','research_progress');
          checkCapacity(limits,'context_references',(record.refs??[]).length,'items','research_progress');
          if ((record.step_id == null) !== (record.phase == null)) return failure("agent_task_progress", "invalid_arguments", {
            message: "Provide step_id and phase together, or omit both. Use purpose for a short work title; the host assigns execution step numbers.",
          });
          if (signal?.aborted) return failure("agent_task_progress", "cancelled");
          return success("agent_task_progress", { ...record, refs: record.refs ?? [] });
        } catch(error) { if(error.capacity?.mode==='debug')throw error; return failure("agent_task_progress", "invalid_arguments", {
          message: `Progress arguments must match the published schema: kind is goal, observation, adjustment or limitation; text is 1-${binding.progress_tool_schema.properties.text.maxLength} characters; optional purpose follows the published schema; refs is an array of source references. Omit unused step_id and phase, or provide both: an ASCII identifier and started, updated or completed. Do not send extra fields.`,
        }); }
      },
    }));
  }
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
  register(defineTool({
    name: RESEARCH_TOOL_NAMES[0], label: "Read research state",
    description: "Read committed research state only when needed. Overview is bounded; in a managed research cycle overview.cycle contains the exact current pending_action ID, questions, expected_outputs and checks for recovery. Ledger open_questions are separate from the accepted action questions. Page claims, notes or questions for full text. This does not retrieve Authority results or create evidence.",
    parameters: readParameters,
    async execute(id, params) {
      let input;
      try { input=validate(readParameters,RESEARCH_TOOL_NAMES[0],id,params); }
      catch {
        return failure(RESEARCH_TOOL_NAMES[0],'invalid_arguments',{
          message:'Read arguments do not match this section. Use {section:"overview"} for state, or {section:"notes"|"claims"|"questions",offset,limit} for ledger pages. Use section:"receipt" with request_id only for an update receipt. Omit fields not published for the selected section; use integer offset >= 0 and a positive limit within the published maximum.'});
      }
      try {
        const section = input.section ?? "overview";
        if (section === "receipt") {
          if (typeof input.request_id !== "string" || !ID.test(input.request_id)) return failure(RESEARCH_TOOL_NAMES[0], "invalid_arguments", {
            message: "Receipt lookup requires the request_id returned by agent_research_update. To read current research state, use section overview instead.",
          });
          let raw;
          try { raw = readBytes(join(root, "requests", input.request_id + ".json")); }
          catch (error) {
            if (error?.code === "ENOENT") return failure(RESEARCH_TOOL_NAMES[0], "research_request_not_found", {
              message: "No update request matches this request_id in the current task. Use the request_id returned by agent_research_update, not a research cycle or observation ID. Use section overview to read current state.",
            });
            throw error;
          }
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
        if (input.request_id != null) return failure(RESEARCH_TOOL_NAMES[0], "invalid_arguments", {
          message: "request_id is used only with section receipt. For overview, claims, notes or questions, omit it or use null."
        });
        const view = loadView();
        if (section === "overview") {
          const result=success(RESEARCH_TOOL_NAMES[0], await summary(view,{fullCycle:true,offset:input.offset??0,pageSize:input.limit??8}));
          checkCapacity(limits,'research_response_bytes',Buffer.byteLength(JSON.stringify(result)),'bytes','research_overview');
          return result;
        }
        const records = (view.state?.[section === "questions" ? "open_questions" : section] ?? [])
          .filter(record => !isRecordVisible || isRecordVisible(section,record));
        const offset = input.offset ?? 0, limit = input.limit ?? Math.min(8,binding.read_tool_schema.properties.limit.maximum ?? limits.research_page_records);
        checkCapacity(limits,'research_page_records',limit,'items','research_read');
        return success(RESEARCH_TOOL_NAMES[0], { ...identity(view), section, total: records.length, offset,
          next_offset: offset + limit < records.length ? offset + limit : null, records: records.slice(offset, offset + limit) });
      } catch (error) { if(error.capacity?.mode==='debug')throw error; return failure(RESEARCH_TOOL_NAMES[0], error.capacity?.code ?? 'research_read_failed',error.capacity); }
    },
  }));
  register(defineTool({
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
      try { checkCapacity(limits,'research_request_bytes',Buffer.byteLength(raw),'bytes','research_request'); }
      catch(error) { if(error.capacity?.mode==='debug')throw error; return failure(RESEARCH_TOOL_NAMES[1],error.capacity.code,error.capacity); }
      const requestHash = digest(raw), path = join(root, "requests", requestId + ".json");
      try { await publish(path, raw); }
      catch { return failure(RESEARCH_TOOL_NAMES[1], "research_publication_not_confirmed", { status: "not_confirmed", request_id: requestId }); }
      const deadline = Date.now() + (timeoutMs ?? limits.tool_timeout_seconds * 1000);
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
  register(defineTool({
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
    preparedGraphRequest = null;
    if (view.state !== null) {
      let graph = false;
      const content = PREFIX + JSON.stringify(await summary(view, {captureGraph: value => { graph = value; }}));
      // Child settlement can advance the live checkpoint after this hook.
      // Validate the exact prepared turn, not a second mutable graph summary.
      if (graph) preparedGraphRequest = {content, meaning: researchMeaning(view)};
      messages.push({role: "custom", customType: CUSTOM_TYPE, content, display: false, timestamp: 0});
    }
    return { messages };
  });
  pi.on("before_model_request", async event => {
    // Pi runs its summary request outside transformContext during compaction.
    // This phase is set by trusted lifecycle events, never by prompt text.
    if (compacting) return;
    try {
      const view = loadView();
      if (view.state === null) return;
      let expected;
      const prepared = preparedGraphRequest;
      preparedGraphRequest = null;
      if (prepared) {
        if (prepared.meaning !== researchMeaning(view)) throw new Error('research meaning changed before the prepared request');
        expected = prepared.content;
      } else {
        let graph = false;
        expected = PREFIX + JSON.stringify(await summary(view, {captureGraph: value => { graph = value; }}));
        if (graph) throw new Error('graph request has no prepared context');
      }
      const count = event.context.messages.filter(message => message.role === "user" &&
        (typeof message.content === "string" ? message.content === expected
          : message.content?.some(part => part.type === "text" && part.text === expected))).length;
      if (count !== 1) throw new Error("current research state is absent or duplicated in the model request");
    } catch(error) { if(error.capacity?.mode==='debug')throw error; return fatal("research context is not ready for the model request"); }
  });
  pi.on("session_before_compact", () => { compacting = true; preparedGraphRequest = null; });
  pi.on("session_compact", () => { compacting = false; });
  pi.on("session_compact_failed", () => { compacting = false; });

  // Trusted application adapters use the exact same validation, CAS request,
  // receipt recovery and context guard as model-facing research updates.
  // This is not another state store and it does not bypass source admission.
  return Object.freeze({
    readResearch: () => structuredClone(loadView()),
    commitResearch: (requestId, params, signal) => registered.get(RESEARCH_TOOL_NAMES[1]).execute(requestId, params, signal),
  });

  async function publish(path, raw) {
    verifyDirectories();
    const temporary = join(root, "requests", "." + randomUUID() + ".tmp");
    const handle = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | O_NOFOLLOW, 0o600);
    let published = false;
    try {
      await handle.writeFile(raw); await handle.sync(); await handle.close();
      verifyDirectories();
      try { await link(temporary, path); published = true; }
      catch (error) {
        if (error?.code !== "EEXIST" || JSON.stringify(readJson(path)) !== JSON.stringify(JSON.parse(raw))) throw error;
      }
      const directory = await open(join(root, "requests"), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
      try { await directory.sync(); } finally { await directory.close(); }
      verifyDirectories();
    } finally {
      await handle.close().catch(() => {});
      // Removing a published inode's temporary hardlink changes its ctime.
      // Keep this hidden anchor until existing whole-task cleanup so strict
      // concurrent readers never mistake normal publication for mutation.
      if (!published) await unlink(temporary).catch(() => {});
    }
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
