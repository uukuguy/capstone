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
  legacyDescriptorToRuntimeV1,
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

const runtimeV1 = Object.freeze({
  schema: "capability-agent-runtime/1.0",
  application: Object.freeze({ applicationId: "fixture-app", runId: "run-1" }),
  core: Object.freeze({
    decisionToolName: "agent_record_decision",
    contextToolName: "agent_context_get",
  }),
  domains: Object.freeze([
    Object.freeze({
      bindingId: "inventory",
      protocol: "inventory-capability",
      protocolVersion: "1.0",
      executable: "inventoryctl",
      executableArgs: Object.freeze([
        "request",
        "--workspace",
        "/tmp/run/domains/inventory",
      ]),
      toolCatalogPath: "/tmp/run/domains/inventory/tool-catalog.json",
      guideToolName: "inventory_guide_open",
      guideIndexPath: "/tmp/run/domains/inventory/guide-index.json",
      guideRootPath: "/tmp/run/domains/inventory/guides",
      guideIndexSha256: "a".repeat(64),
      workspacePath: "/tmp/run/domains/inventory",
      authorityId: "inventoryctl",
    }),
  ]),
});

test("validates one binding-aware runtime descriptor", () => {
  const descriptor = validateRuntimeDescriptor(runtimeV1);

  assert.equal(descriptor.schema, "capability-agent-runtime/1.0");
  assert.equal(descriptor.domains.length, 1);
  assert.equal(descriptor.domains[0].bindingId, "inventory");
  assert.equal(descriptor.domains[0].authorityId, "inventoryctl");
  assert.equal(Object.isFrozen(descriptor), true);
  assert.equal(Object.isFrozen(descriptor.application), true);
  assert.equal(Object.isFrozen(descriptor.core), true);
  assert.equal(Object.isFrozen(descriptor.domains), true);
  assert.equal(Object.isFrozen(descriptor.domains[0]), true);
});

test("runtime v1 rejects unknown keys and any domain count except one", () => {
  for (const invalid of [
    { ...runtimeV1, unexpected: true },
    { ...runtimeV1, application: { ...runtimeV1.application, unexpected: true } },
    { ...runtimeV1, core: { ...runtimeV1.core, unexpected: true } },
    {
      ...runtimeV1,
      domains: [{ ...runtimeV1.domains[0], unexpected: true }],
    },
    { ...runtimeV1, domains: [] },
    { ...runtimeV1, domains: [runtimeV1.domains[0], runtimeV1.domains[0]] },
  ]) {
    assert.throws(() => validateRuntimeDescriptor(invalid), /runtime descriptor/);
  }
});

test("runtime v1 confines domain-owned paths to the binding workspace", () => {
  for (const field of ["toolCatalogPath", "guideIndexPath", "guideRootPath"]) {
    const invalid = {
      ...runtimeV1,
      domains: [{ ...runtimeV1.domains[0], [field]: `/tmp/outside/${field}` }],
    };
    assert.throws(
      () => validateRuntimeDescriptor(invalid),
      new RegExp(`${field}.*outside.*workspacePath`),
    );
  }
  assert.throws(
    () =>
      validateRuntimeDescriptor({
        ...runtimeV1,
        domains: [
          {
            ...runtimeV1.domains[0],
            executableArgs: ["request", "--workspace", "/tmp/outside"],
          },
        ],
      }),
    /executableArgs.*outside.*workspacePath/,
  );
});

test("routes a capability only through the controller-selected binding", async () => {
  const payloads = [];
  const tool = createCapabilityTool(
    runtimeV1,
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

  await tool.execute("call-1", { value: "controller-bound" });

  assert.equal(payloads.length, 1);
  assert.equal(payloads[0].protocol, "inventory-capability");
  assert.equal(payloads[0].protocol_version, "1.0");
  assert.equal(payloads[0].capability, "asset.list");
  assert.deepEqual(payloads[0].arguments, { value: "controller-bound" });
});

test("model arguments cannot select controller-owned routing metadata", () => {
  for (const field of [
    "binding",
    "bindingId",
    "binding_id",
    "executable",
    "executableArgs",
    "executable_args",
    "protocol",
    "protocolVersion",
    "protocol_version",
    "authority",
    "authorityId",
    "authority_id",
    "workspace",
    "workspacePath",
    "workspace_path",
  ]) {
    assert.throws(
      () => buildCapabilityRequest(runtimeV1, "asset.list", { [field]: "attacker" }, "r-1"),
      /controller-owned routing field/,
    );
  }
});

test("converts the legacy descriptor through an explicit compatibility path", () => {
  const converted = legacyDescriptorToRuntimeV1(inventory);

  assert.equal(converted.schema, "capability-agent-runtime/1.0");
  assert.equal(converted.application.applicationId, "legacy-capability-agent");
  assert.equal(converted.core.contextToolName, "inventory_analysis_context_get");
  assert.equal(converted.core.decisionToolName, "inventory_record_decision");
  assert.equal(converted.domains[0].bindingId, "inventory");
  assert.equal(converted.domains[0].authorityId, "inventoryctl");
  assert.equal(converted.domains[0].protocol, "inventory-capability");
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

test("generic source has no product-specific protocol, executable, prefix, or environment literals", async () => {
  const sourceRoot = dirname(fileURLToPath(import.meta.url)).replace(/[/\\]test$/, "/src");
  const source = `${await readFile(join(sourceRoot, "domain-tools.mjs"), "utf8")}\n${await readFile(
    join(sourceRoot, "model-request-capture.mjs"),
    "utf8",
  )}`;

  for (const forbidden of [/grid[-_]/i, /pandapower/i]) {
    assert.equal(forbidden.test(source), false, `generic source contains ${forbidden}`);
  }
  assert.equal(source.includes("realpath(resourcePath)"), false);
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
