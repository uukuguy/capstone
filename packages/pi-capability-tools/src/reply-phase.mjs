import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "@earendil-works/pi-ai";
import { constants, openSync, closeSync, fstatSync, readFileSync, lstatSync, realpathSync, writeFileSync, fsyncSync, renameSync, unlinkSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { isAbsolute, join, resolve } from "node:path";

/** The agent selects delivery; the next native turn has no executable tools. */
export function configureReplyPhase(pi, { attemptId, read, write }) {
  let originalTools, requested = null;
  const state = () => {
    const value = read();
    if (value.schema !== "capstone-reply-phase/1" || value.attempt_id !== attemptId
      || !["research", "reply"].includes(value.phase)) throw new Error("reply phase binding is invalid");
    return value;
  };
  pi.on("agent_start", () => {
    if (originalTools === undefined) originalTools = [...pi.getActiveTools()];
    requested = null;
    pi.setActiveTools(state().phase === "reply" ? [] : originalTools);
  });
  pi.on("turn_end", () => {
    if (requested === null) return;
    write({ schema: "capstone-reply-phase/1", attempt_id: attemptId, phase: "reply", agent_outcome: requested });
    requested = null;
    pi.setActiveTools([]);
  });
  pi.on("context", event => {
    const binding = state();
    const messages = event.messages.filter(message =>
      !(message.role === "custom" && message.customType === "capstone-formal-reply"));
    if (binding.phase === "reply") messages.push({
      role: "custom", customType: "capstone-formal-reply", display: false, timestamp: 0,
      content: "Write the formal reply now for the original user request. "
        + `The agent selected outcome: ${binding.agent_outcome}. `
        + "Use the collected observations, calculation results and evidence. State the conclusions, "
        + "material assumptions, failed work and unresolved limits. Distinguish verified findings "
        + "from proposals and unavailable results. Match the user's language. Do not claim unperformed "
        + "calculations or successful checks. No execution tools are available in this reply call.",
    });
    return { messages };
  });
  pi.on("before_model_request", event => {
    if (state().phase === "reply" && event.context.tools.length !== 0)
      throw new Error("reply request still contains executable tools");
  });
  pi.registerTool(defineTool({
    name: "capstone_begin_reply", label: "进入正式回复",
    description: "Enter the formal reply phase after the required investigation or a supported partial outcome. Schedule this with the last planned tool batch when possible. The host waits for that turn to finish, then removes all tool definitions before the reply model call. Use the collected observations, results, evidence and failures. This records the agent's decision, not scientific verification. It does not calculate, discard data, or mark the task verified.",
    parameters: Type.Object({ outcome: Type.Union([Type.Literal("completed"), Type.Literal("partial"), Type.Literal("blocked")]),
      execution_purpose: Type.Optional(Type.String({ minLength: 1, maxLength: 120 })) }, { additionalProperties: false }),
    async execute(_id, args) {
      if (Object.keys(args).some(key => !["outcome", "execution_purpose"].includes(key))
        || !["completed", "partial", "blocked"].includes(args.outcome)) {
        return { isError: true, content: [{ type: "text", text: "Reply phase request is invalid. Saved work is retained." }],
          details: { event: "tool_result", capability: "capstone_begin_reply", ok: false,
            request_parameters: args, result_refs: [], evidence_refs: [],
            error: { code: "invalid_reply_phase", message: "Reply phase request is invalid.", phase: "validate" } } };
      }
      requested = args.outcome;
      return { content: [{ type: "text", text: JSON.stringify({ status: "scheduled", next_phase: "reply", agent_outcome: args.outcome }) }],
        details: { event: "tool_result", capability: "capstone_begin_reply", ok: true,
          request_parameters: args, requested_phase: "reply", agent_outcome: args.outcome,
          result_refs: [], evidence_refs: [] } };
    },
  }));
}

export default function replyPhase(pi) {
  const directory = process.env.CAPSTONE_REPLY_PHASE;
  if (!directory) return;
  if (!isAbsolute(directory) || realpathSync(directory) !== resolve(directory)) throw new Error("reply directory is invalid");
  const root = resolve(directory), pinned = lstatSync(root), path = join(root, "phase.json");
  if (!pinned.isDirectory() || pinned.isSymbolicLink()) throw new Error("reply directory is invalid");
  const verify = () => {
    const current = lstatSync(root);
    if (current.dev !== pinned.dev || current.ino !== pinned.ino || current.isSymbolicLink()) throw new Error("reply directory changed");
  };
  const read = () => {
    verify();
    const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const stat = fstatSync(fd);
      if (!stat.isFile() || stat.size > 8192) throw new Error("reply state is invalid");
      return JSON.parse(readFileSync(fd, "utf8"));
    } finally { closeSync(fd); }
  };
  const write = value => {
    verify();
    const temporary = join(root, `.${randomUUID()}.tmp`);
    const fd = openSync(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    try { writeFileSync(fd, JSON.stringify(value) + "\n"); fsyncSync(fd); } finally { closeSync(fd); }
    try { verify(); if (lstatSync(path).isSymbolicLink()) throw new Error("reply state changed"); renameSync(temporary, path); }
    finally { try { unlinkSync(temporary); } catch (error) { if (error.code !== "ENOENT") throw error; } }
  };
  const binding = read();
  configureReplyPhase(pi, { attemptId: binding.attempt_id, read, write });
}
