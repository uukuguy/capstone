import { readFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { applicationToolAdmission, guardToolExecution, researchExecutionPort } from "./general-sdk.mjs";
import {runtimeLimits, checkCapacity, CapacityExceeded} from './runtime-limits.mjs';

// The host supplies one fixed local server and schemas. Tool arguments cannot
// select a process, endpoint, credentials or installation.
export class BoundedMcp {
  constructor(config) {
    this.config = config; this.calls = 0; this.pending = null; this.closed = false;
    this.limits = runtimeLimits({...JSON.parse(readFileSync(new URL('./application-capacity.json', import.meta.url), 'utf8')).limits,
      ...config.runtimeLimits}, {mode: config.runtimeLimitMode ?? 'normal'});
  }
  close(error = new Error("MCP outcome unknown; do not retry")) {
    this.closed = true;
    this.child?.kill("SIGKILL");
    this.lines?.close();
    this.pending?.reject(error);
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
    const ready = this.wait(signal, (this.limits.mcp_initialize_seconds + this.limits.mcp_catalog_seconds) * 1000);
    this.child = spawn(config.interpreter, ["-I", "-B", "-c",
      "import sys;sys.path.insert(0,'/opt/general');from capstone_agent.bounded_mcp import main;main()", config.configPath],
      { cwd: config.mcp.workspace, env: { PATH: "/usr/local/bin:/usr/bin:/bin", HOME: config.mcp.workspace,
        LANG: "C.UTF-8", PYTHONDONTWRITEBYTECODE: "1", PYTHONNOUSERSITE: "1" }, stdio: ["pipe", "pipe", "ignore"] });
    this.lines = createInterface({ input: this.child.stdout });
    this.lines.on("line", line => {
      try {
        checkCapacity(this.limits, 'mcp_frame_bytes', Buffer.byteLength(line), 'bytes', 'mcp_result');
        const frame = JSON.parse(line);
        if (frame.error === 'capacity_exceeded' && frame.capacity &&
            Object.hasOwn(this.limits, frame.capacity.dimension)) {
          throw new CapacityExceeded(this.limits, frame.capacity.dimension, frame.capacity.actual,
            frame.capacity.unit, frame.capacity.phase);
        }
        if (frame.error) throw new Error("MCP outcome unknown; do not retry");
        const pending = this.pending; this.pending = null;
        if (!pending) throw new Error("Unexpected MCP frame");
        pending.resolve(frame);
      } catch (error) { this.close(error instanceof CapacityExceeded ? error : undefined); }
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
    checkCapacity(this.limits, 'mcp_call_count', ++this.calls, 'items', 'mcp_call');
    if (!Object.hasOwn(this.config.mcp.descriptor.tool_schemas, name)) {
      this.close(); throw new Error("MCP tool name is invalid");
    }
    const body = JSON.stringify({ name, arguments: arguments_ });
    checkCapacity(this.limits, 'mcp_frame_bytes', Buffer.byteLength(body), 'bytes', 'mcp_arguments');
    const response = this.wait(signal, this.limits.mcp_tool_seconds * 1000);
    this.child.stdin.write(body + "\n");
    return response;
  }
}

export async function configureGeneralMcp(pi,config,{bridge=new BoundedMcp(config),research=()=>researchExecutionPort(config)}={}) {
  if (!config.mcp) return;
  for (const [name, schema] of Object.entries(config.mcp.descriptor.tool_schemas)) {
    pi.registerTool(guardToolExecution({ name, label: name, description: schema.description ?? name,
      parameters: schema.inputSchema,
      execute: async (id, args, signal) => {
        const controller=research();
        if(config.researchRuntime?.enabled&&!controller)throw new Error('The protected research controller is unavailable; do not execute unplanned work.');
        const token=await controller?.beginTool({toolCallId:id,toolName:name});
        let value;
        try {value = await bridge.call(name, args, signal);}
        catch(error){controller?.endTool(token,undefined,error);throw error;}
        const result={ content: [{ type: "text", text: value.result_json }], details: value.observation,
          isError: value.is_error === true };
        controller?.endTool(token,result);return result;
      } }, async call => applicationToolAdmission(config, call.toolName)));
  }
  pi.on("session_start", async () => { if (config.inventoryOnly) await bridge.start(); });
  pi.on("session_shutdown", async () => bridge.close());
}

export default async function(pi){return configureGeneralMcp(pi,JSON.parse(readFileSync(process.argv[2],"utf8")));}
