import { createHash } from "node:crypto";
import { constants, openSync, closeSync, fstatSync, readFileSync, realpathSync, lstatSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import {runtimeLimits as resolveLimits,checkCapacity,sameRuntimeLimits} from './runtime-limits.mjs';

/** Only read host-published pages of the task explicitly selected by the user. */
export function configureTaskRecordTool(pi, directory, {runtimeLimits}={}) {
  let limits=resolveLimits(runtimeLimits);
  if (!isAbsolute(directory) || realpathSync(directory) !== resolve(directory)) throw new Error("task records directory is invalid");
  const root = resolve(directory), pinned = lstatSync(root);
  if (!pinned.isDirectory() || pinned.isSymbolicLink()) throw new Error("task records directory is invalid");
  function read(name) {
    const current = lstatSync(root);
    if (current.dev !== pinned.dev || current.ino !== pinned.ino || current.isSymbolicLink()) throw new Error("task records directory changed");
    const fd = openSync(join(root, name), constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const stat = fstatSync(fd);
      if (!stat.isFile()) throw new Error('task record page is invalid');
      checkCapacity(limits,'control_document_bytes',stat.size,'bytes','task_records_read');
      const data = readFileSync(fd);
      checkCapacity(limits,'control_document_bytes',data.length,'bytes','task_records_read');
      return data;
    } finally { closeSync(fd); }
  }
  const manifest = JSON.parse(read("manifest.json"));
  if(manifest.runtime_limits !== undefined && runtimeLimits !== undefined && !sameRuntimeLimits(manifest.runtime_limits,runtimeLimits)) {
    throw new Error('task records runtime_limits differ from initialized reader limits');
  }
  limits=resolveLimits({...manifest.runtime_limits,...runtimeLimits});
  if (manifest.schema !== "capstone-selected-task-input/1" || !Array.isArray(manifest.pages)
      || !manifest.pages.every(p => Number.isSafeInteger(p.after) && p.after >= 0 && /^[a-f0-9]{64}$/.test(p.sha256))) {
    throw new Error("task records manifest is invalid");
  }
  pi.registerTool({
    name: "agent_task_records_read", label: "读取原任务记录",
    description: "Read execution records of the historical task selected by the user. Includes tool parameters, outcomes and failures. Historical records are not evidence for a new calculation. Use next_after while has_more is true.",
    parameters: { type: "object", properties: { after: { type: "integer", minimum: 0 } }, additionalProperties: false },
    async execute(_callId, args) {
      try {
        const after = args.after ?? 0;
        if (Object.keys(args).some(k => k !== "after") || !Number.isSafeInteger(after) || after < 0) throw new Error("invalid cursor");
        const entry = manifest.pages.find(p => p.after === after);
        if (!entry) throw new Error("unknown cursor");
        const bytes = read(`${after}.json`);
        if (createHash("sha256").update(bytes).digest("hex") !== entry.sha256) throw new Error("task record bytes changed");
        const page = JSON.parse(bytes);
        if (page.schema !== "capstone-selected-task-records/1" || page.historical_only !== true
            || page.thread_id !== manifest.thread_id || page.attempt_id !== manifest.attempt_id) throw new Error("task identity mismatch");
        return { content: [{ type: "text", text: JSON.stringify(page) }],
          details: { event: "tool_result", capability: "agent_task_records_read", ok: true,
            request_parameters: { after }, result: page, evidence_refs: [] } };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: "Original task records could not be read. The saved history remains available." }],
          details: { event: "tool_result", capability: "agent_task_records_read", ok: false,
            error: error.capacity ?? { code: "selected_task_records_unavailable", message: "Original task records could not be read.", phase: "read" },
            evidence_refs: [], historical_only: true } };
      }
    },
  });
}

export default function taskRecordTools(pi) {
  const directory = process.env.CAPSTONE_SELECTED_TASK_RECORDS;
  if (directory) configureTaskRecordTool(pi, directory);
}
