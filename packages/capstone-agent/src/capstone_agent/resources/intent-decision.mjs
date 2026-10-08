// Trusted application output hook. This tool cannot call an authority or a shell.
const strings = { type: "array", items: { type: "string" } };
const goal = {
  type: "object", additionalProperties: false,
  required: ["goal_id", "description", "operation", "message_refs", "object_refs", "capability_refs", "missing_requirements", "depends_on"],
  properties: {
    goal_id: { type: "string", minLength: 1 },
    description: { type: "string", minLength: 1 },
    operation: { type: "string", enum: ["answer", "rewrite", "catalog_lookup", "external_lookup", "business_read", "business_execute"] },
    message_refs: strings, object_refs: strings, capability_refs: strings,
    missing_requirements: strings, depends_on: strings,
  },
};

export default function (pi) {
  pi.registerTool({
    name: "capstone_intent_decision", label: "Request decision",
    description: "Finish request understanding with one structured decision. This grants no execution permission.",
    parameters: {
      type: "object", additionalProperties: false,
      required: ["schema", "attempt_id", "history_cutoff", "relationship", "goals", "clarification"],
      properties: {
        schema: { type: "string", const: "capstone-intent-decision/1" },
        attempt_id: { type: "string", minLength: 1 },
        history_cutoff: { type: "integer", minimum: 0 },
        relationship: { type: "string", enum: ["independent", "continuation", "supplement", "unclear"] },
        goals: { type: "array", minItems: 1, items: goal },
        clarification: { anyOf: [{ type: "string", minLength: 1 }, { type: "null" }] },
      },
    },
    async execute(_callId, params) {
      return {
        content: [{ type: "text", text: "Request decision submitted." }],
        details: { capability: "capstone.intent.decision", ok: true, result: params },
        terminate: true,
      };
    },
  });
  pi.on("session_start", async () => pi.setActiveTools(["capstone_intent_decision"]));
}
