import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Managed runtime context, separate from the professional policy and tools.
export default function (pi) {
  const context = JSON.parse(readFileSync(resolve(process.cwd(), "context.json"), "utf8"));
  pi.on("context", async (event, ctx) => {
    const history = context.messages.map((message) => message.role === "user"
      ? { role: "user", content: message.content, timestamp: 0 }
      : { role: "assistant", content: [{ type: "text", text: message.content }],
          api: ctx.model.api, provider: ctx.model.provider, model: ctx.model.id,
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
          stopReason: "stop", timestamp: 0 });
    const observations = context.dependency_results.length
      ? [{ role: "user", content: JSON.stringify({ external_task_observations: context.dependency_results }), timestamp: 0 }]
      : [];
    return { messages: [...history, ...observations, ...event.messages] };
  });
}
