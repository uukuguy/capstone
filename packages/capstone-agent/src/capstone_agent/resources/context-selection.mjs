// Trusted selection output. This hook has no execution or Authority tools.
import { readFileSync } from "node:fs";

export default function (pi) {
  const projection = JSON.parse(readFileSync(process.env.CAPSTONE_PI_CONTEXT_PATH, "utf8"));
  const request = projection.supplemental_context.request;
  const references = (ids, limit) => ({ type: "array", uniqueItems: true,
    maxItems: Math.min(ids.length, limit),
    items: ids.length ? { type: "string", enum: ids } : { type: "string" } });
  pi.registerTool({
    name: "capstone_context_selection", label: "Select task context",
    description: "Select public business objects and conversation messages for a direct task. This grants no authority.",
    parameters: { type: "object", additionalProperties: false,
      required: ["schema", "attempt_id", "history_cutoff", "object_refs", "message_refs", "clarification_required", "clarification"],
      properties: {
        schema: { type: "string", const: "capstone-context-selection-decision/1" },
        attempt_id: { type: "string", const: request.attempt_id },
        history_cutoff: { type: "integer", const: request.history_cutoff },
        object_refs: references(request.objects.map((item) => item.object_id), 16),
        message_refs: references([...projection.messages.map((item) => item.message_id), request.instruction_message_id], 32),
        clarification_required: { type: "boolean" },
        clarification: { anyOf: [{ type: "string", minLength: 1, maxLength: 8192 }, { type: "null" }] },
      } },
    async execute(_callId, params) {
      return { content: [{ type: "text", text: "Task context selection submitted." }],
        details: { capability: "capstone.context.selection", ok: true, result: params }, terminate: true };
    },
  });
  pi.on("session_start", async () => pi.setActiveTools(["capstone_context_selection"]));
}
