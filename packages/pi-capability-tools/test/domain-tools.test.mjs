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

test("runtime v1 reserves the agent namespace from every domain tool name", () => {
  assert.throws(
    () =>
      validateRuntimeDescriptor({
        ...runtimeV1,
        domains: [
          {
            ...runtimeV1.domains[0],
            guideToolName: "agent_domain_guide_open",
          },
        ],
      }),
    /agent_.*reserved|reserved.*agent_/,
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
  const completeCapture = {
    activeTurnPath: "/tmp/run/domains/inventory/active.json",
    trajectoryRequestsPath: "/tmp/run/domains/inventory/requests",
    trajectoryCaptureStatePath: "/tmp/run/domains/inventory/capture.json",
    trajectoryAllowedRefsPath: "/tmp/run/domains/inventory/refs.json",
    trajectoryAcksPath: "/tmp/run/domains/inventory/acks",
  };
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
          core: { ...runtimeV1.core, ...completeCapture, [field]: `/tmp/outside/${field}` },
        }),
      new RegExp(`${field}.*outside.*workspacePath`),
    );
  }
});

test("runtime v1 rejects partial model request capture channels", () => {
  assert.throws(
    () => validateRuntimeDescriptor({
      ...runtimeV1,
      core: {
        ...runtimeV1.core,
        trajectoryRequestsPath: "/tmp/run/domains/inventory/requests",
      },
    }),
    /capture channels/,
  );
  const capture = {
    trajectoryRequestsPath: "/tmp/run/domains/inventory/requests",
    trajectoryCaptureStatePath: "/tmp/run/domains/inventory/capture.json",
    trajectoryAllowedRefsPath: "/tmp/run/domains/inventory/refs.json",
    trajectoryAcksPath: "/tmp/run/domains/inventory/acks",
  };
  assert.throws(
    () => validateRuntimeDescriptor({ ...runtimeV1, core: { ...runtimeV1.core, ...capture } }),
    /capture channels/,
  );
  assert.doesNotThrow(() => validateRuntimeDescriptor({
    ...runtimeV1,
    core: {
      ...runtimeV1.core,
      activeTurnPath: "/tmp/run/domains/inventory/active.json",
      ...capture,
    },
  }));
});

test("runtime v1 separates application core paths from the domain workspace", () => {
  const split = {
    ...runtimeV1,
    application: {
      ...runtimeV1.application,
      workspacePath: "/tmp/run",
    },
    core: {
      ...runtimeV1.core,
      analysisContextViewPath: "/tmp/run/core/context.json",
    },
  };

  assert.doesNotThrow(() => validateRuntimeDescriptor(split));
  assert.throws(
    () =>
      validateRuntimeDescriptor({
        ...split,
        core: {
          ...split.core,
          analysisContextViewPath: "/tmp/outside/context.json",
        },
      }),
    /analysisContextViewPath.*outside.*workspacePath/,
  );
  assert.throws(
    () =>
      validateRuntimeDescriptor({
        ...split,
        domains: [
          {
            ...split.domains[0],
            toolCatalogPath: "/tmp/run/core/tool-catalog.json",
          },
        ],
      }),
    /toolCatalogPath.*outside.*workspacePath/,
  );
});

test("generic extension accepts a split application and domain workspace", async () => {
  const fixture = await runtimeV1Fixture();
  const applicationWorkspace = join(fixture.root, "run");
  const corePath = join(applicationWorkspace, "core", "context.json");
  await mkdir(dirname(corePath), { recursive: true });
  await writeFile(corePath, "{}", "utf8");
  const descriptor = {
    ...fixture.descriptor,
    application: {
      ...fixture.descriptor.application,
      workspacePath: applicationWorkspace,
    },
    core: {
      ...fixture.descriptor.core,
      analysisContextViewPath: corePath,
    },
  };
  const registered = [];

  createDomainToolsExtension(descriptor)({
    registerTool: (tool) => registered.push(tool.name),
  });

  assert.deepEqual(registered, ["inventory_guide_open", "agent_context_get"]);
});

test("default extension factory reads only the controller runtime descriptor", async () => {
  const fixture = await runtimeV1Fixture();
  const descriptorPath = join(fixture.root, "runtime-descriptor.json");
  await writeFile(descriptorPath, JSON.stringify(fixture.descriptor), "utf8");
  const previousDescriptor = process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
  const previousLegacyCatalog = process.env.GRID_AGENT_TOOL_CATALOG;
  process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = descriptorPath;
  process.env.GRID_AGENT_TOOL_CATALOG = join(fixture.root, "missing-catalog.json");

  try {
    const extensionModule = await import("../src/domain-tools.mjs");
    assert.equal(typeof extensionModule.default, "function");
    const registered = [];
    extensionModule.default({ registerTool: (tool) => registered.push(tool.name) });
    assert.deepEqual(registered, ["inventory_guide_open"]);
  } finally {
    if (previousDescriptor === undefined) {
      delete process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
    } else {
      process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = previousDescriptor;
    }
    if (previousLegacyCatalog === undefined) {
      delete process.env.GRID_AGENT_TOOL_CATALOG;
    } else {
      process.env.GRID_AGENT_TOOL_CATALOG = previousLegacyCatalog;
    }
  }
});

test("default extension factory rejects descriptor symlinks and oversized files", async () => {
  const fixture = await runtimeV1Fixture();
  const descriptorPath = join(fixture.root, "runtime-descriptor.json");
  const symlinkPath = join(fixture.root, "runtime-descriptor-link.json");
  const oversizedPath = join(fixture.root, "runtime-descriptor-large.json");
  await writeFile(descriptorPath, JSON.stringify(fixture.descriptor), "utf8");
  await symlink(descriptorPath, symlinkPath);
  await writeFile(oversizedPath, "{" + "x".repeat(1_048_576) + "}", "utf8");
  const extensionModule = await import("../src/domain-tools.mjs");
  const previousDescriptor = process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;

  try {
    process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = symlinkPath;
    assert.throws(
      () => extensionModule.default({ registerTool: () => undefined }),
      /CAPABILITY_AGENT_RUNTIME_DESCRIPTOR/,
    );
    process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = oversizedPath;
    assert.throws(
      () => extensionModule.default({ registerTool: () => undefined }),
      /CAPABILITY_AGENT_RUNTIME_DESCRIPTOR/,
    );
  } finally {
    if (previousDescriptor === undefined) {
      delete process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
    } else {
      process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = previousDescriptor;
    }
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
      projector_id: "inventory-state-v1",
      result_kind: "asset.catalog",
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

  const output = await tool.execute("call-1", { value: "controller-bound" });

  assert.equal(payloads.length, 1);
  assert.equal(payloads[0].protocol, "inventory-capability");
  assert.equal(payloads[0].protocol_version, "1.0");
  assert.equal(payloads[0].capability, "asset.list");
  assert.deepEqual(payloads[0].arguments, { value: "controller-bound" });
  assert.deepEqual(output.details.capability_key, {
    binding_id: "inventory",
    capability_id: "asset.list",
  });
  assert.equal(output.details.projector_id, "inventory-state-v1");
  assert.equal(output.details.result_kind, "asset.catalog");
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
    "binding-id", "executable-args", "protocol-version", "authority-id", "workspace-path",
    "tool-catalog-path", "guide-tool-name", "guide-index-path", "guide-root-path",
    "guide-index-sha256", "context-tool-name", "decision-tool-name", "active-turn-path",
    "analysis-context-view-path", "trajectory-requests-path", "trajectory-capture-state-path",
    "trajectory-allowed-refs-path", "trajectory-acks-path",
    "args", "arguments", "endpoint", "endpointPath", "endpoint_path", "endpoint-path",
    "command", "commandArgs", "command_args", "command-args",
    "toolNamePrefix", "tool_name_prefix", "tool-name-prefix",
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

test("model arguments reject every controller routing stem and control suffix combination before invoke", async () => {
  const routingFields = ["endpoint", "command", "executable"].flatMap((stem) =>
    ["path", "command", "args", "arguments"].flatMap((suffix) => {
      const capitalizedSuffix = `${suffix[0].toUpperCase()}${suffix.slice(1)}`;
      return [
        `${stem}${capitalizedSuffix}`,
        `${stem}_${suffix}`,
        `${stem}-${suffix}`,
      ];
    }),
  );
  const payloads = [];
  const tool = createCapabilityTool(
    runtimeV1,
    contract("inventory_asset_list", "asset.list"),
    async (payload) => {
      payloads.push(payload);
      return {
        protocol: payload.protocol,
        protocol_version: payload.protocol_version,
        request_id: payload.request_id,
        ok: true,
        result: {},
      };
    },
  );

  for (const field of routingFields) {
    await assert.rejects(
      () => tool.execute("routing-alias", { [field]: "attacker" }),
      /controller-owned routing field/,
      field,
    );
  }
  assert.deepEqual(payloads, []);
});

test("model arguments retain business result and status fields", () => {
  const params = {
    command_result: "complete",
    endpoint_status: "available",
    executable_summary: "bounded controller output",
  };

  const request = buildCapabilityRequest(runtimeV1, "asset.list", params, "business-fields");

  assert.deepEqual(request.arguments, params);
});

test("catalog collision preflight has zero tool creation or registration side effects", async () => {
  const fixture = await runtimeV1Fixture();
  const collisionCatalogs = [
    [contract("inventory_asset_list", "asset.list"), contract("inventory_asset_list", "asset.get")],
    [contract("inventory_guide_open", "guide.shadow")],
    [contract("agent_record_decision", "core.shadow")],
    [contract("agent_context_get", "context.shadow")],
    [contract("agent_domain_tool", "domain.shadow")],
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

test("spawn rejects absolute executable argument paths that escape through symlinks", async () => {
  const fixture = await runtimeV1Fixture();
  const outsideFile = join(fixture.root, "outside-argument.json");
  const outsideDirectory = join(fixture.root, "outside-argument-directory");
  await writeFile(outsideFile, "{}", "utf8");
  await mkdir(outsideDirectory);
  const existingLink = join(fixture.workspace, "existing-argument-link");
  const parentLink = join(fixture.workspace, "argument-parent-link");
  await symlink(outsideFile, existingLink);
  await symlink(outsideDirectory, parentLink);

  for (const argument of [existingLink, join(parentLink, "new-output.json")]) {
    const descriptor = {
      ...fixture.descriptor,
      domains: [
        {
          ...fixture.descriptor.domains[0],
          executableArgs: ["request", argument],
        },
      ],
    };
    const payload = buildCapabilityRequest(descriptor, "asset.list", {}, "escape-request");

    assert.throws(
      () => runCapability(payload, descriptor),
      /executableArgs.*outside.*workspacePath/,
    );
  }
});

test("spawn accepts existing and future absolute arguments confined to the workspace", async () => {
  const fixture = await runtimeV1Fixture();
  const transport = await transportFixture(`
    let input = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { input += chunk; });
    process.stdin.on("end", () => {
      const request = JSON.parse(input);
      process.stdout.write(JSON.stringify({
        protocol: request.protocol,
        protocol_version: request.protocol_version,
        request_id: request.request_id,
        ok: true,
        result: {},
      }));
    });
  `);
  const existingPath = join(fixture.workspace, "existing-input.json");
  const futurePath = join(fixture.workspace, "future-output.json");
  await writeFile(existingPath, "{}", "utf8");
  const descriptor = {
    ...fixture.descriptor,
    domains: [
      {
        ...fixture.descriptor.domains[0],
        executable: transport.name,
        executableArgs: [existingPath, futurePath],
      },
    ],
  };
  const payload = buildCapabilityRequest(descriptor, "asset.list", {}, "confined-request");
  const originalPath = process.env.PATH;
  process.env.PATH = `${transport.bin}:${originalPath ?? ""}`;

  try {
    const response = await runCapability(payload, descriptor);
    assert.equal(response.ok, true);
    assert.equal(response.request_id, "confined-request");
  } finally {
    process.env.PATH = originalPath;
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

test("legacy catalog permits at most one decision alias", async () => {
  const fixture = await runtimeV1Fixture();
  await writeFile(
    fixture.catalogPath,
    JSON.stringify({
      tools: [
        contract("inventory_record_decision", "inventory_record_decision"),
        contract("inventory_record_decision", "inventory_record_decision"),
      ],
    }),
    "utf8",
  );
  const domain = fixture.descriptor.domains[0];
  const legacy = {
    ...inventory,
    executableArgs: ["request", "--workspace", fixture.workspace],
    toolCatalogPath: domain.toolCatalogPath,
    guideIndexPath: domain.guideIndexPath,
    guideRootPath: domain.guideRootPath,
    guideIndexSha256: domain.guideIndexSha256,
    workspacePath: domain.workspacePath,
  };
  let created = 0;
  let registered = 0;

  assert.throws(
    () =>
      createDomainToolsExtension(legacy, {
        createTool() {
          created += 1;
          return { name: "unexpected" };
        },
      })({ registerTool: () => { registered += 1; } }),
    /tool name collision/,
  );
  assert.equal(created, 0);
  assert.equal(registered, 0);
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
  )}\n${await readFile(
    join(sourceRoot, "process-transport.mjs"),
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

test("transport rejects a successful JSON response from a failed process", async () => {
  const fixture = await transportFixture(`
    let input = "";
    process.stdin.on("data", (chunk) => { input += chunk; });
    process.stdin.on("end", () => {
      const request = JSON.parse(input);
      const response = JSON.stringify({
        protocol: request.protocol,
        protocol_version: request.protocol_version,
        request_id: request.request_id,
        ok: true,
        result: {},
      });
      process.stdout.write(response, () => process.exit(7));
    });
  `);
  const payload = buildCapabilityRequest(inventory, "asset.list", {}, "failed-process-request");
  const originalPath = process.env.PATH;
  process.env.PATH = `${fixture.bin}:${originalPath ?? ""}`;

  try {
    const response = await runCapability(
      payload,
      { ...inventory, executable: fixture.name, executableArgs: [] },
    );
    assert.equal(response.ok, false);
    assert.equal(response.error.code, "capability_transport_process_failed");
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
    projector_id: "inventory-state-v1",
    result_kind: "asset.catalog",
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
