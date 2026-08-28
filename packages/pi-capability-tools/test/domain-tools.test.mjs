import test from "node:test";
import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  buildCapabilityRequest,
  createCapabilityTool,
  createDomainToolsExtension,
  runCapability,
  sanitizeEnvironment,
  validateRuntimeDescriptor,
} from "../src/domain-tools.mjs";

const inventory = Object.freeze({
  protocol: "inventory-capability",
  protocolVersion: "1.0",
  executable: "inventoryctl",
  executableArgs: ["request", "--workspace", "/tmp/inventory-run"],
  toolNamePrefix: "inventory_",
  guideToolName: "inventory_guide_open",
  contextToolName: "inventory_analysis_context_get",
  decisionToolName: "inventory_record_decision",
});

test("builds a descriptor-owned capability request", () => {
  assert.deepEqual(buildCapabilityRequest(inventory, "asset.list", {}, "r-1"), {
    protocol: "inventory-capability",
    protocol_version: "1.0",
    request_id: "r-1",
    capability: "asset.list",
    arguments: {},
  });
});

test("rejects invalid runtime descriptors before tool creation", () => {
  for (const invalid of [
    { ...inventory, unexpected: true },
    { ...inventory, executable: "/tmp/inventoryctl" },
    { ...inventory, executableArgs: ["request", 42] },
    { ...inventory, toolNamePrefix: "inventory" },
    { ...inventory, guideToolName: "other_guide_open" },
    { ...inventory, contextToolName: "other_analysis_context_get" },
    { ...inventory, decisionToolName: "other_record_decision" },
  ]) {
    assert.throws(() => validateRuntimeDescriptor(invalid), /runtime descriptor/);
  }
});

test("rejects unbounded capability contract names before tool creation", () => {
  const contract = {
    name: "inventory_asset_list",
    capability: "asset.list",
    description: "List assets",
    input_schema: { type: "object", additionalProperties: false, properties: {} },
  };

  for (const name of ["shell", "other_asset_list", "inventory_"]) {
    assert.throws(
      () => createCapabilityTool(inventory, { ...contract, name }, async () => undefined),
      /tool prefix/,
    );
  }
});

test("requires the exact four keys in descriptor Pi runtime identity", () => {
  const runtime = {
    pi_coding_agent_version: "0.80.6",
    pi_ai_version: "0.80.6",
    pi_source_commit: "a".repeat(40),
    pi_patch_set_sha256: "b".repeat(64),
  };
  const symbol = Symbol("unexpected");

  assert.doesNotThrow(() => validateRuntimeDescriptor({ ...inventory, piRuntime: runtime }));
  assert.throws(
    () => validateRuntimeDescriptor({ ...inventory, piRuntime: { ...runtime, provider: "secret" } }),
    /piRuntime.*unknown field/,
  );
  assert.throws(
    () => validateRuntimeDescriptor({ ...inventory, piRuntime: { ...runtime, [symbol]: "unexpected" } }),
    /piRuntime.*unknown field/,
  );
  const { pi_patch_set_sha256: _hash, ...missing } = runtime;
  assert.throws(
    () => validateRuntimeDescriptor({ ...inventory, piRuntime: missing }),
    /piRuntime.*keys/,
  );
});

test("fails closed when a capability response has the wrong correlation", async () => {
  const tool = createCapabilityTool(
    inventory,
    {
      name: "inventory_asset_list",
      capability: "asset.list",
      description: "List assets",
      input_schema: { type: "object", additionalProperties: false, properties: {} },
    },
    async () => ({
      protocol: "inventory-capability",
      protocol_version: "1.0",
      request_id: "wrong-request",
      ok: true,
      result: {},
    }),
  );

  const result = await tool.execute("call-1", {});

  assert.equal(result.isError, true);
  assert.equal(result.details.error.code, "response_correlation_mismatch");
});

test("keeps process selection outside model-owned tool parameters", async () => {
  const payloads = [];
  const tool = createCapabilityTool(
    inventory,
    {
      name: "inventory_asset_list",
      capability: "asset.list",
      description: "List assets",
      input_schema: { type: "object", additionalProperties: false, properties: {} },
    },
    async (payload) => {
      payloads.push(payload);
      return {
        protocol: "inventory-capability",
        protocol_version: "1.0",
        request_id: payload.request_id,
        ok: true,
        result: { assets: [] },
      };
    },
  );

  await tool.execute("call-1", {
    executable: "attacker",
    executableArgs: ["--dangerous"],
    protocol: "attacker-capability",
    value: "kept-as-argument",
  });

  assert.deepEqual(payloads, [
    {
      protocol: "inventory-capability",
      protocol_version: "1.0",
      request_id: payloads[0].request_id,
      capability: "asset.list",
      arguments: {
        executable: "attacker",
        executableArgs: ["--dangerous"],
        protocol: "attacker-capability",
        value: "kept-as-argument",
      },
    },
  ]);
  assert.match(payloads[0].request_id, /^[0-9a-f-]{36}$/);
});

test("generic source has no product-specific protocol, executable, prefix, or environment literals", async () => {
  const sourceRoot = dirname(fileURLToPath(import.meta.url)).replace(/[/\\]test$/, "/src");
  const source = `${await readFile(join(sourceRoot, "domain-tools.mjs"), "utf8")}\n${await readFile(
    join(sourceRoot, "model-request-capture.mjs"),
    "utf8",
  )}`;

  for (const forbidden of [/grid[-_]/i, /pandapower/i]) {
    assert.equal(forbidden.test(source), false, `generic source contains ${forbidden}`);
  }
});

test("sanitizes credentials without requiring a product namespace", () => {
  assert.deepEqual(
    sanitizeEnvironment(
      {
        PATH: "/safe/bin",
        OPENAI_API_KEY: "secret",
        CUSTOM_PROVIDER_TOKEN: "secret",
        CAPABILITY_AGENT_SECRET_ENV_NAMES: "CUSTOM_PROVIDER_TOKEN",
      },
      ["OPENAI_API_KEY", "CUSTOM_PROVIDER_TOKEN"],
    ),
    { PATH: "/safe/bin" },
  );
});

test("transport terminates a timed-out capability with a structured error", async () => {
  const fixture = await transportFixture(
    `setTimeout(() => {
      const request = JSON.parse(process.env.REQUEST_JSON);
      process.stdout.write(JSON.stringify({
        protocol: request.protocol,
        protocol_version: request.protocol_version,
        request_id: request.request_id,
        ok: true,
        result: {},
      }));
    }, 200);`,
  );
  const payload = buildCapabilityRequest(inventory, "asset.list", {}, "timeout-request");
  const originalPath = process.env.PATH;
  process.env.PATH = `${fixture.bin}:${originalPath ?? ""}`;
  process.env.REQUEST_JSON = JSON.stringify(payload);

  try {
    const response = await runCapability(
      payload,
      { ...inventory, executable: fixture.name, executableArgs: [] },
      [],
      { timeoutMs: 20, maxOutputBytes: 4096 },
    );
    assert.equal(response.ok, false);
    assert.equal(response.error.code, "capability_transport_timeout");
  } finally {
    delete process.env.REQUEST_JSON;
    process.env.PATH = originalPath;
  }
});

test("transport caps stdout bytes with a structured error", async () => {
  const fixture = await transportFixture(`process.stdout.write("x".repeat(8192));`);
  const payload = buildCapabilityRequest(inventory, "asset.list", {}, "output-limit-request");
  const originalPath = process.env.PATH;
  process.env.PATH = `${fixture.bin}:${originalPath ?? ""}`;

  try {
    const response = await runCapability(
      payload,
      { ...inventory, executable: fixture.name, executableArgs: [] },
      [],
      { timeoutMs: 1000, maxOutputBytes: 1024 },
    );
    assert.equal(response.ok, false);
    assert.equal(response.error.code, "capability_transport_output_limit");
  } finally {
    process.env.PATH = originalPath;
  }
});

test("registers descriptor-prefixed bounded tools", async () => {
  const registered = [];
  const descriptor = Object.freeze({
    ...inventory,
    workspacePath: "/tmp/inventory-run",
    toolCatalogPath: "/tmp/inventory-tool-catalog.json",
    guideIndexPath: "/tmp/inventory-guide-index.json",
  });

  const extension = createDomainToolsExtension(descriptor);
  assert.throws(
    () => extension({ registerTool: (tool) => registered.push(tool) }),
    /workspacePath path/,
  );
  assert.deepEqual(registered, []);
});

async function transportFixture(body) {
  const root = await mkdtemp(join(tmpdir(), "capability-transport-"));
  const bin = join(root, "bin");
  const name = "transport-fixture";
  const executable = join(bin, name);
  await mkdir(bin);
  await writeFile(executable, `#!/usr/bin/env node\n${body}\n`, "utf8");
  await chmod(executable, 0o755);
  return { bin, name };
}
