import { readFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

// The host supplies one fixed local server and schemas. Tool arguments cannot
// select a process, endpoint, credentials or installation.
export class BoundedMcp {
  constructor(config) { this.config = config; this.calls = 0; this.pending = null; this.closed = false; }
  close() {
    this.closed = true;
    this.child?.kill("SIGKILL");
    this.lines?.close();
    this.pending?.reject(new Error("MCP outcome unknown; do not retry"));
    this.pending = null;
  }
  wait(signal, limit) {
    if (this.closed || signal?.aborted || this.pending) throw new Error("MCP connection unavailable");
    const remaining = Math.min(limit, this.config.deadlineAt - Date.now());
    if (remaining <= 0) { this.close(); throw new Error("MCP deadline exceeded; do not retry"); }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.close(), remaining);
      const abort = () => this.close();
      signal?.addEventListener("abort", abort, { once: true });
      const finish = fn => value => { clearTimeout(timer); signal?.removeEventListener("abort", abort); fn(value); };
      this.pending = { resolve: finish(resolve), reject: finish(reject) };
    });
  }
  async start(signal) {
    if (this.child) return;
    const config = this.config;
    const ready = this.wait(signal, 60000);
    this.child = spawn(config.interpreter, ["-I", "-B", "-c",
      "import sys;sys.path.insert(0,'/opt/general');from capstone_agent.bounded_mcp import main;main()", config.configPath],
      { cwd: config.mcp.workspace, env: { PATH: "/usr/local/bin:/usr/bin:/bin", HOME: config.mcp.workspace,
        LANG: "C.UTF-8", PYTHONDONTWRITEBYTECODE: "1", PYTHONNOUSERSITE: "1" }, stdio: ["pipe", "pipe", "ignore"] });
    this.lines = createInterface({ input: this.child.stdout });
    this.lines.on("line", line => {
      try {
        if (Buffer.byteLength(line) > 131072) throw new Error("MCP result exceeds bounds");
        const frame = JSON.parse(line);
        if (frame.error) throw new Error("MCP outcome unknown; do not retry");
        const pending = this.pending; this.pending = null;
        if (!pending) throw new Error("Unexpected MCP frame");
        pending.resolve(frame);
      } catch { this.close(); }
    });
    this.child.on("error", () => this.close());
    this.child.on("exit", () => this.close());
    const frame = await ready;
    if (frame.type !== "mcp_ready" || JSON.stringify(frame.tool_schema_hashes) !== JSON.stringify(config.mcp.descriptor.tool_schema_hashes)) {
      this.close(); throw new Error("MCP publication changed");
    }
  }
  async call(name, arguments_, signal) {
    await this.start(signal);
    if (++this.calls > 32 || !Object.hasOwn(this.config.mcp.descriptor.tool_schemas, name)) {
      this.close(); throw new Error("MCP call limit or name is invalid");
    }
    const body = JSON.stringify({ name, arguments: arguments_ });
    if (Buffer.byteLength(body) > 131072) throw new Error("MCP arguments exceed bounds");
    const response = this.wait(signal, 30000);
    this.child.stdin.write(body + "\n");
    return response;
  }
}

export default async function(pi) {
  const config = JSON.parse(readFileSync(process.argv[2], "utf8"));
  if (!config.mcp) return;
  const bridge = new BoundedMcp(config);
  for (const [name, schema] of Object.entries(config.mcp.descriptor.tool_schemas)) {
    pi.registerTool({ name, label: name, description: schema.description ?? name,
      parameters: schema.inputSchema,
      execute: async (_id, args, signal) => {
        const value = await bridge.call(name, args, signal);
        return { content: [{ type: "text", text: value.result_json }], details: value.observation,
                 isError: value.is_error === true };
      } });
  }
  pi.on("session_start", async () => { if (config.inventoryOnly) await bridge.start(); });
  pi.on("session_shutdown", async () => bridge.close());
}
