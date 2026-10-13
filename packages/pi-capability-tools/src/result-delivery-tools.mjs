import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "@earendil-works/pi-ai";
import { createHash, randomUUID } from "node:crypto";
import { constants, openSync, closeSync, fstatSync, readFileSync, realpathSync, lstatSync } from "node:fs";
import { open, link, unlink } from "node:fs/promises";
import { isAbsolute, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

/** Application presentation only. No simulator calls, endpoints or model-chosen paths. */
export function configureResultDeliveryTool(pi, directory, { timeoutMs = 30000 } = {}) {
  if (!isAbsolute(directory) || realpathSync(directory) !== resolve(directory)) throw new Error("delivery directory is invalid");
  const root = resolve(directory);
  const pinned = [root, join(root, "requests"), join(root, "receipts")].map(path => {
    const stat = lstatSync(path);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error("delivery directory is invalid");
    return [path, stat.dev, stat.ino];
  });
  const verify = () => {
    for (const [path, dev, ino] of pinned) {
      const stat = lstatSync(path);
      if (stat.dev !== dev || stat.ino !== ino || stat.isSymbolicLink() || realpathSync(path) !== path) throw new Error("delivery directory changed");
    }
  };
  function read(path) {
    verify();
    const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const before = fstatSync(fd, { bigint: true });
      if (!before.isFile() || before.size > 1048576n) throw new Error("delivery file is invalid");
      const bytes = readFileSync(fd), after = fstatSync(fd, { bigint: true }), named = lstatSync(path, { bigint: true });
      const identity = stat => [stat.dev, stat.ino, stat.size, stat.mtimeNs, stat.ctimeNs].join(":");
      if (identity(before) !== identity(after) || identity(after) !== identity(named)) throw new Error("delivery file changed");
      verify();
      return bytes;
    } finally { closeSync(fd); }
  }
  const binding = JSON.parse(read(join(root, "binding.json")));
  const id = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
  if (binding.schema !== "capstone-result-delivery/1" || !id.test(binding.thread_id) || !id.test(binding.attempt_id)) throw new Error("delivery identity is invalid");
  pi.registerTool(defineTool({
    name: "capstone_result_delivery_read", label: "准备结果表格交付",
    description: "Prepare complete result tables for the user's 计算结果 view and read its verified delivery receipt. Use an observed result_ref from this attempt. Returns table fields, sourced row counts, completeness and summary; full table rows stay in the application output, not in this receipt. This does not calculate or create evidence. Final answer admission is still pending. After confirmed coverage, explain the outcome and key findings without retyping the delivered table rows. For extra analysis use the published domain query tools; report unavailable or partial coverage accurately.",
    parameters: Type.Object({ result_ref: Type.String({ minLength: 1, maxLength: 512 }),
      execution_purpose: Type.String({ minLength: 1, maxLength: 240 }) }, { additionalProperties: false }),
    async execute(_callId, args, signal) {
      try {
        if (Object.keys(args).some(k => !["result_ref", "execution_purpose"].includes(k))
          || typeof args.result_ref !== "string" || !args.result_ref || args.result_ref.length > 512
          || typeof args.execution_purpose !== "string" || !args.execution_purpose || args.execution_purpose.length > 240) throw new Error("invalid delivery request");
        verify();
        const requestId = randomUUID(), path = join(root, "requests", `${requestId}.json`), temporary = `${path}.tmp`;
        const bytes = JSON.stringify({ request_id: requestId, thread_id: binding.thread_id,
          attempt_id: binding.attempt_id, result_ref: args.result_ref });
        const file = await open(temporary, "wx", 0o600);
        try { await file.writeFile(bytes); await file.sync(); } finally { await file.close(); }
        try { verify(); await link(temporary, path); } finally { await unlink(temporary); }
        const hash = createHash("sha256").update(bytes).digest("hex"), started = Date.now();
        while (Date.now() - started < timeoutMs) {
          signal?.throwIfAborted();
          let receipt;
          try { receipt = JSON.parse(read(join(root, "receipts", `${requestId}.json`))); }
          catch (error) { if (error.code !== "ENOENT") throw error; }
          if (receipt) {
            if (receipt.schema !== "capstone-result-delivery-receipt/1" || receipt.thread_id !== binding.thread_id
              || receipt.attempt_id !== binding.attempt_id || receipt.request_id !== requestId || receipt.request_sha256 !== hash) throw new Error("delivery receipt binding differs");
            const ok = receipt.status === "prepared";
            return { isError: !ok, content: [{ type: "text", text: JSON.stringify(receipt) }],
              details: { event: "tool_result", capability: "capstone_result_delivery_read", ok,
                request_parameters: args, presentation_receipt: receipt,
                error: ok ? undefined : { code: receipt.code, message: receipt.message ?? "Result table delivery is unavailable; existing results are retained.", phase: "presentation" },
                result_refs: [], evidence_refs: [] } };
          }
          await delay(25, undefined, { signal });
        }
        throw new Error("delivery wait timed out");
      } catch {
        return { isError: true, content: [{ type: "text", text: "Table delivery could not be confirmed. Existing results remain available through published tools." }],
          details: { event: "tool_result", capability: "capstone_result_delivery_read", ok: false,
            request_parameters: args, result_refs: [], evidence_refs: [],
            error: { code: "result_delivery_unavailable", message: "Table delivery could not be confirmed.", phase: "presentation" } } };
      }
    },
  }));
}

export default function resultDeliveryTools(pi) {
  const directory = process.env.CAPSTONE_RESULT_DELIVERY;
  if (directory) configureResultDeliveryTool(pi, directory);
}
