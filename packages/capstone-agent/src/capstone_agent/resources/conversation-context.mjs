import { readFileSync } from "node:fs";

// The application owns this path. It is not a model-facing file tool.
export default function (pi) {
  const path = process.env.CAPSTONE_PI_CONTEXT_PATH;
  if (!path) throw new Error("Conversation context path is missing");
  const projection = JSON.parse(readFileSync(path, "utf8"));
  if (projection.schema !== "capstone-pi-context/1" || !Array.isArray(projection.messages)) {
    throw new Error("Conversation context is invalid");
  }
  pi.on("context", async (event, ctx) => {
    const model = ctx.model;
    const history = projection.messages.flatMap((message) => {
      if (message.role === "user") {
        return [{ role: "user", content: message.content, timestamp: 0 }];
      }
      if (message.role !== "assistant") throw new Error("History role is invalid");
      if (!["completed", "succeeded", "success"].includes(message.status)) return [];
      return [{
        role: "assistant", content: [{ type: "text", text: message.content }],
        api: model.api, provider: model.provider, model: model.id,
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        stopReason: "stop", timestamp: 0,
      }];
    });
    const metadata = projection.messages.map(({ content, ...metadata }) => metadata);
    const resources = {
      schema: projection.schema, attempt_id: projection.attempt_id,
      history_sources: metadata, supplemental_context: projection.supplemental_context,
    };
    return { messages: [...history,
      { role: "user", content: JSON.stringify(resources), timestamp: 0 }, ...event.messages] };
  });
}
