import test from "node:test";
import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, readFile, symlink, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
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

test("runtime v1 requires distinct agent-prefixed core tools", () => {
  for (const core of [
    { decisionToolName: "grid_record_decision", contextToolName: "agent_context_get" },
    { decisionToolName: "agent_record_decision", contextToolName: "grid_context_get" },
    { decisionToolName: "agent_record_decision", contextToolName: "agent_record_decision" },
  ]) {
    assert.throws(
      () => validateRuntimeDescriptor({ ...runtimeV1, core }),
      /runtime descriptor core/,
    );
  }
});

test("runtime v1 rejects a domain guide collision with a core tool", () => {
  const core = {
    decisionToolName: "agent_guide_open",
    contextToolName: "agent_context_get",
  };
  assert.throws(
    () =>
      validateRuntimeDescriptor({
        ...runtimeV1,
        core,
        domains: [
          {
            ...runtimeV1.domains[0],
            guideToolName: core.decisionToolName,
          },
        ],
      }),
    /tool name collision/,
  );
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

test("runtime v1 confines every optional core path to the binding workspace", () => {
  for (const field of [
    "activeTurnPath",
    "analysisContextViewPath",
    "trajectoryRequestsPath",
    "trajectoryCaptureStatePath",
    "trajectoryAllowedRefsPath",
    "trajectoryAcksPath",
  ]) {
    assert.throws(
      () =>
        validateRuntimeDescriptor({
          ...runtimeV1,
          core: { ...runtimeV1.core, [field]: `/tmp/outside/${field}` },
        }),
      new RegExp(`${field}.*outside.*workspacePath`),
    );
  }
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
  const reservedSpellings = [
    "binding", "bindingId", "binding_id",
    "executable", "executableArgs", "executable_args",
    "protocol", "version", "protocolVersion", "protocol_version",
    "authority", "authorityId", "authority_id",
    "workspace", "workspacePath", "workspace_path",
    "toolCatalogPath", "tool_catalog_path", "toolCatalog", "tool_catalog", "catalogPath", "catalog_path", "catalog",
    "guideToolName", "guide_tool_name", "guideTool", "guide_tool",
    "guideIndexPath", "guide_index_path", "guideIndex", "guide_index",
    "guideRootPath", "guide_root_path", "guideRoot", "guide_root",
    "guideIndexSha256", "guide_index_sha256", "guideDigest", "guide_digest",
    "contextToolName", "context_tool_name", "contextTool", "context_tool",
    "decisionToolName", "decision_tool_name", "decisionTool", "decision_tool",
    "activeTurnPath", "active_turn_path",
    "analysisContextViewPath", "analysis_context_view_path",
    "trajectoryRequestsPath", "trajectory_requests_path",
    "trajectoryCaptureStatePath", "trajectory_capture_state_path",
    "trajectoryAllowedRefsPath", "trajectory_allowed_refs_path",
    "trajectoryAcksPath", "trajectory_acks_path",
  ];
  for (const field of reservedSpellings) {
    assert.throws(
      () => buildCapabilityRequest(runtimeV1, "asset.list", { [field]: "attacker" }, "r-1"),
      /controller-owned routing field/,
    );
  }
  assert.throws(
    () => buildCapabilityRequest(runtimeV1, "asset.list", { [Symbol("binding")]: "attacker" }, "r-1"),
    /controller-owned routing field/,
  );
});

test("catalog collision preflight has zero tool creation or registration side effects", async () => {
  const fixture = await runtimeV1Fixture();
  const collisionCatalogs = [
    [contract("inventory_asset_list", "asset.list"), contract("inventory_asset_list", "asset.get")],
    [contract("inventory_guide_open", "guide.shadow")],
    [contract("agent_record_decision", "core.shadow")],
    [contract("agent_context_get", "context.shadow")],
  ];

  for (const tools of collisionCatalogs) {
    await writeFile(fixture.catalogPath, JSON.stringify({ tools }), "utf8");
    let created = 0;
    let registered = 0;
    const extension = createDomainToolsExtension(fixture.descriptor, {
      createTool() {
        created += 1;
        return { name: "unexpected" };
      },
    });

    assert.throws(
      () => extension({ registerTool: () => { registered += 1; } }),
      /tool name collision/,
    );
    assert.equal(created, 0);
    assert.equal(registered, 0);
  }
});

test("runtime realpath confinement rejects core and guide symlink escapes", async () => {
  for (const category of ["trajectoryAcksPath", "guideRootPath"]) {
    const fixture = await runtimeV1Fixture({ withTrajectory: category === "trajectoryAcksPath" });
    const outside = join(fixture.root, `outside-${category}`);
    if (category === "guideRootPath") {
      await mkdir(outside);
    } else {
      await writeFile(outside, "{}", "utf8");
    }
    const link = join(fixture.workspace, `linked-${category}`);
    await symlink(outside, link);
    const descriptor = category === "guideRootPath"
      ? {
          ...fixture.descriptor,
          domains: [{ ...fixture.descriptor.domains[0], guideRootPath: link }],
        }
      : {
          ...fixture.descriptor,
          core: { ...fixture.descriptor.core, trajectoryAcksPath: link },
        };
    let registered = 0;

    assert.throws(
      () => createDomainToolsExtension(descriptor)({ registerTool: () => { registered += 1; } }),
      new RegExp(`${category}.*outside.*workspacePath`),
    );
    assert.equal(registered, 0);
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

test("legacy conversion rejects collisions among its valid alias names", () => {
  for (const invalid of [
    { ...inventory, contextToolName: inventory.guideToolName },
    { ...inventory, decisionToolName: inventory.guideToolName },
    { ...inventory, decisionToolName: inventory.contextToolName },
  ]) {
    assert.throws(() => legacyDescriptorToRuntimeV1(invalid), /tool name collision/);
  }
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

function contract(name, capability) {
  return {
    name,
    capability,
    description: `Fixture ${capability}`,
    input_schema: { type: "object", additionalProperties: false, properties: {} },
  };
}

async function runtimeV1Fixture({ withTrajectory = false } = {}) {
  const root = await mkdtemp(join(tmpdir(), "capability-runtime-v1-"));
  const workspace = join(root, "run/domains/inventory");
  const guideRootPath = join(workspace, "guides");
  const catalogPath = join(workspace, "tool-catalog.json");
  const guideIndexPath = join(workspace, "guide-index.json");
  await mkdir(guideRootPath, { recursive: true });
  await writeFile(catalogPath, JSON.stringify({ tools: [] }), "utf8");
  const guideIndex = JSON.stringify({
    protocol: "inventory-guide-index",
    version: "1.0",
    root: guideRootPath,
    resources: {},
  });
  await writeFile(guideIndexPath, guideIndex, "utf8");
  const core = { ...runtimeV1.core };
  if (withTrajectory) {
    const trajectoryRequestsPath = join(workspace, "trajectory-requests");
    await mkdir(trajectoryRequestsPath);
    const paths = {
      activeTurnPath: join(workspace, "active-turn.json"),
      trajectoryCaptureStatePath: join(workspace, "capture-state.json"),
      trajectoryAllowedRefsPath: join(workspace, "allowed-refs.json"),
      trajectoryAcksPath: join(workspace, "acks.json"),
    };
    await Promise.all(Object.values(paths).map((path) => writeFile(path, "{}", "utf8")));
    Object.assign(core, paths, { trajectoryRequestsPath });
  }
  return {
    root,
    workspace,
    catalogPath,
    descriptor: {
      ...runtimeV1,
      core,
      domains: [
        {
          ...runtimeV1.domains[0],
          executableArgs: ["request", "--workspace", workspace],
          toolCatalogPath: catalogPath,
          guideIndexPath,
          guideRootPath,
          guideIndexSha256: createHash("sha256").update(guideIndex).digest("hex"),
          workspacePath: workspace,
        },
      ],
    },
  };
}

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
