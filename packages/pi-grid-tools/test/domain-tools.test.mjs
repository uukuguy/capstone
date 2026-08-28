import test from "node:test";
import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import domainToolsExtension, {
  buildGridRequest,
  createGridTool,
  sanitizeEnvironment,
} from "../src/domain-tools.mjs";

test("registers catalog tools and guide without model-owned answer submission", async () => {
  const root = await makeFixtureRoot();
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);

  const registered = [];
  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });

  assert.equal(
    registered.some((tool) => tool.name === "grid_submit_answer"),
    false,
  );
  assert.deepEqual(
    registered.map((tool) => tool.name).sort(),
    [
      "grid_environment_describe",
      "grid_guide_open",
      "grid_topology_branch_endpoints",
    ],
  );
  const legacyQuery = "grid" + "_query";
  for (const forbidden of ["bash", "read", "write", "edit", legacyQuery]) {
    assert.equal(registered.some((tool) => tool.name === forbidden), false);
  }
  assert.deepEqual(
    registered.find((tool) => tool.name === "grid_topology_branch_endpoints").parameters,
    {
      type: "object",
      additionalProperties: false,
      required: ["context_ref"],
      properties: { context_ref: { type: "string" } },
    },
  );
  assert.equal(
    registered.find((tool) => tool.name === "grid_guide_open")
      .parameters.properties.resource_id.pattern,
    "a^",
  );
});

test("registers newly published static-analysis tools directly from the catalog", async () => {
  const root = await makeFixtureRoot();
  clearOptionalAnalysisEnvironment();
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  const extraTools = [
    ["grid_model_equivalent_derive", "model.equivalent.derive"],
    ["grid_analysis_result_violations_evaluate", "analysis.result.violations.evaluate"],
    ["grid_analysis_result_risk_rank", "analysis.result.risk.rank"],
  ].map(([name, capability]) => ({
    name,
    capability,
    description: `Purpose: ${capability}`,
    input_schema: { type: "object", additionalProperties: false, properties: {} },
  }));
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG, extraTools);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);

  const registered = [];
  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });

  for (const [name] of extraTools.map((tool) => [tool.name])) {
    assert.equal(registered.some((tool) => tool.name === name), true);
  }
});

test("production extension reads controller-owned runtime descriptor before legacy paths", async () => {
  const root = await makeFixtureRoot();
  const descriptorPath = join(root, "run/pi/domain-runtime.json");
  await mkdir(join(root, "run/pi"), { recursive: true });
  await writeCatalog(join(root, "run/tool-catalog.json"));
  await writeGuideIndex(join(root, "run/guide-index.json"), root);
  process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = descriptorPath;
  process.env.GRID_AGENT_WORKSPACE = join(root, "missing-run");
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "missing-tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "missing-guide-index.json");
  await writeRuntimeDescriptor(descriptorPath, root);

  const registered = [];
  try {
    domainToolsExtension({ registerTool: (tool) => registered.push(tool) });
  } finally {
    delete process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
  }

  assert.deepEqual(
    registered.map((tool) => tool.name).sort(),
    [
      "grid_environment_describe",
      "grid_guide_open",
      "grid_topology_branch_endpoints",
    ],
  );
});

test("descriptor mode rejects missing authoritative paths instead of supplementing legacy env", async () => {
  const root = await makeFixtureRoot();
  const descriptorPath = join(root, "run/pi/domain-runtime.json");
  process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = descriptorPath;
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);
  await mkdir(join(root, "run/pi"), { recursive: true });
  await writeRuntimeDescriptor(descriptorPath, root, { workspace_path: undefined });

  try {
    assert.throws(
      () => domainToolsExtension({ registerTool: () => undefined }),
      /workspace_path must be a non-empty string/,
    );
  } finally {
    delete process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
  }
});

test("production extension rejects arbitrary executable runtime descriptors", async () => {
  const root = await makeFixtureRoot();
  await configureDescriptorAndLegacyPaths(root, { executable: "bash" });

  assert.throws(
    () => domainToolsExtension({ registerTool: () => undefined }),
    /CAPABILITY_AGENT_RUNTIME_DESCRIPTOR executable must be gridctl/,
  );

  delete process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
});

test("production extension rejects runtime descriptors outside the grid contract", async () => {
  const cases = [
    { protocol: "inventory-capability" },
    { tool_name_prefix: "inventory_" },
    { guide_tool_name: "inventory_guide_open" },
  ];

  for (const overrides of cases) {
    const root = await makeFixtureRoot();
    await configureDescriptorAndLegacyPaths(root, overrides);
    assert.throws(
      () => domainToolsExtension({ registerTool: () => undefined }),
      /CAPABILITY_AGENT_RUNTIME_DESCRIPTOR .* must be /,
    );
    delete process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR;
  }
});

test("analysis tools expose bounded context without model-owned answer submission", async () => {
  const root = await makeFixtureRoot();
  await configureAnalysisPaths(
    root,
    {
      turn_id: "analysis-test-t002",
      turn_nonce: "nonce-2",
    },
    { schema_version: "analysis-context-view/1.0", revision: 9, state_hash: "sha256:test" },
  );

  const registered = [];
  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });

  assert.equal(registered.some((tool) => tool.name === "grid_analysis_context_get"), true);
  assert.equal(registered.some((tool) => tool.name === "grid_submit_answer"), false);
  const context = await registered.find((tool) => tool.name === "grid_analysis_context_get").execute("context-1", {});

  assert.equal(context.isError, undefined);
  assert.equal(context.details.result.revision, 9);
});

test("analysis context tool is optional for legacy single-run launches", async () => {
  const root = await makeFixtureRoot();
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  delete process.env.GRID_AGENT_ACTIVE_TURN;
  delete process.env.GRID_AGENT_ANALYSIS_CONTEXT_VIEW;
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);

  const registered = [];
  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });

  assert.equal(registered.some((tool) => tool.name === "grid_analysis_context_get"), false);
  assert.equal(registered.some((tool) => tool.name === "grid_submit_answer"), false);
});

test("startup accepts future writable active-turn file inside workspace", async () => {
  const root = await makeFixtureRoot();
  clearOptionalAnalysisEnvironment();
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  process.env.GRID_AGENT_ACTIVE_TURN = join(root, "run/active-turn.json");
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);

  const registered = [];
  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });

  assert.equal(registered.some((tool) => tool.name === "grid_record_decision"), false);
});

test("records bounded decisions only against controller-known refs", async () => {
  const { registered, root } = await configuredNativeTools();
  const known = "result:sha256:" + "a".repeat(64);
  await writeFile(
    join(root, "run/context/trajectory-allowed-refs.json"),
    JSON.stringify({ refs: [known] }),
    "utf8",
  );
  const decision = registered.find((tool) => tool.name === "grid_record_decision");

  const accepted = await decision.execute("decision-1", {
    intent: "Assess line 17 N-1 security",
    decision: "Run the published contingency capability",
    next_action: "Resolve line 17 and execute N-1",
    refs: [known],
  });
  const rejected = await decision.execute("decision-2", {
    intent: "Assess",
    decision: "Guess",
    next_action: "Answer",
    refs: ["result:sha256:" + "b".repeat(64)],
  });
  const outOfBounds = await decision.execute("decision-3", {
    intent: "x".repeat(501),
    decision: "Guess",
    next_action: "Answer",
    refs: [],
  });

  assert.equal(accepted.isError, undefined);
  assert.equal(accepted.details.capability, "grid_record_decision");
  assert.deepEqual(accepted.details.result.refs, [known]);
  assert.equal(rejected.isError, true);
  assert.equal(rejected.details.error.code, "unknown_decision_ref");
  assert.equal(outOfBounds.isError, true);
  assert.equal(outOfBounds.details.error.code, "invalid_decision");
});

test("native request capture subscribes to before_model_request only", async () => {
  const root = await makeFixtureRoot();
  await configureAnalysisPaths(
    root,
    { turn_id: "analysis-test-t002", turn_nonce: "nonce-2" },
    { schema_version: "analysis-context-view/1.0", revision: 9, state_hash: "sha256:test" },
  );
  process.env.GRID_AGENT_TRAJECTORY_REQUESTS = join(root, "run/requests");
  process.env.GRID_AGENT_TRAJECTORY_CAPTURE_STATE = join(
    root,
    "run/context/trajectory-capture-state.json",
  );
  process.env.GRID_AGENT_TRAJECTORY_ALLOWED_REFS = join(
    root,
    "run/context/trajectory-allowed-refs.json",
  );
  process.env.GRID_AGENT_TRAJECTORY_ACKS = join(root, ".grid-agent/trajectory-acks/analysis-test");
  await mkdir(process.env.GRID_AGENT_TRAJECTORY_REQUESTS, { recursive: true });
  await mkdir(process.env.GRID_AGENT_TRAJECTORY_ACKS, { recursive: true });
  await writeFile(
    process.env.GRID_AGENT_TRAJECTORY_CAPTURE_STATE,
    JSON.stringify({
      source_event_sequences: [1],
      context_revision: 1,
      context_state_hash: "a".repeat(64),
    }),
    "utf8",
  );
  await writeFile(
    process.env.GRID_AGENT_TRAJECTORY_ALLOWED_REFS,
    JSON.stringify({ refs: [] }),
    "utf8",
  );
  const handlers = new Map();

  domainToolsExtension({
    on: (name, handler) => handlers.set(name, handler),
    registerTool: () => undefined,
  });

  assert.equal(handlers.has("before_model_request"), true);
  assert.equal(handlers.has("before_provider_request"), false);
});

test("removes provider credentials from gridctl child environment", () => {
  const clean = sanitizeEnvironment(
    {
      PATH: "/safe/bin",
      OPENAI_API_KEY: "openai-secret",
      CUSTOM_PROVIDER_TOKEN: "custom-secret",
      GRID_AGENT_SECRET_ENV_NAMES: "CUSTOM_PROVIDER_TOKEN",
    },
    ["OPENAI_API_KEY", "CUSTOM_PROVIDER_TOKEN"],
  );

  assert.deepEqual(clean, { PATH: "/safe/bin" });
});

test("default extension spawn removes a custom provider secret name", async () => {
  const root = await makeFixtureRoot();
  clearOptionalAnalysisEnvironment();
  const bin = join(root, "bin");
  const executable = join(bin, "gridctl");
  await mkdir(bin);
  await writeFile(
    executable,
    `#!/usr/bin/env node
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
    result: { secret_visible: process.env.LLM_ACCESS !== undefined },
  }));
});
`,
    "utf8",
  );
  await chmod(executable, 0o755);
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  process.env.GRID_AGENT_SECRET_ENV_NAMES = "LLM_ACCESS";
  process.env.LLM_ACCESS = "must-not-cross-boundary";
  const originalPath = process.env.PATH;
  process.env.PATH = `${bin}:${originalPath ?? ""}`;
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);
  const registered = [];

  try {
    domainToolsExtension({ registerTool: (tool) => registered.push(tool) });
    const tool = registered.find((candidate) => candidate.name === "grid_environment_describe");
    const result = await tool.execute("secret-boundary", {});
    assert.equal(result.isError, undefined);
    assert.equal(result.details.result.secret_visible, false);
  } finally {
    delete process.env.GRID_AGENT_SECRET_ENV_NAMES;
    delete process.env.LLM_ACCESS;
    process.env.PATH = originalPath;
  }
});

test("builds capability protocol requests with correlation ids", () => {
  assert.deepEqual(buildGridRequest("model.element.get", { identifier: "11" }, "req-1"), {
    protocol: "grid-capability",
    protocol_version: "1.0",
    request_id: "req-1",
    capability: "model.element.get",
    arguments: { identifier: "11" },
  });
});

test("grid request compatibility remains exact", () => {
  assert.deepEqual(buildGridRequest("model.list", {}, "request-1"), {
    protocol: "grid-capability",
    protocol_version: "1.0",
    request_id: "request-1",
    capability: "model.list",
    arguments: {},
  });
});

test("rejects legacy and non-grid capability tool names", () => {
  for (const name of [
    "python",
    "exec",
    "file_read",
    "grid" + "_query",
    "topology_branch_endpoints_get",
  ]) {
    assert.throws(
      () =>
        createGridTool(
          {
            name,
            capability: "unsafe.capability",
            description: "Unsafe capability",
            input_schema: { type: "object", additionalProperties: false, properties: {} },
          },
          async () => undefined,
        ),
      /descriptor tool prefix/,
    );
  }
});

test("maps typed gridctl errors to tool errors", async () => {
  const tool = createGridTool(
    {
      name: "grid_context_open",
      capability: "context.open",
      description: "Open context",
      input_schema: { type: "object", additionalProperties: false, properties: {} },
    },
    async (payload) => ({
      protocol: "grid-capability",
      protocol_version: "1.0",
      request_id: payload.request_id,
      ok: false,
      error: { code: "model_not_found", phase: "resolve", message: "missing model" },
    }),
  );

  const result = await tool.execute("call-1", {});

  assert.equal(result.isError, true);
  assert.deepEqual(result.details.error, {
    code: "model_not_found",
    phase: "resolve",
    message: "missing model",
  });
});

test("returns canonical typed tool-result details for successful gridctl calls", async () => {
  const evidenceRef = "evidence:sha256:" + "a".repeat(64);
  const tool = createGridTool(
    {
      name: "grid_topology_branch_endpoints",
      capability: "topology.branch.endpoints.get",
      description: "Endpoints",
      input_schema: { type: "object", additionalProperties: false, properties: {} },
    },
    async (payload) => ({
      protocol: "grid-capability",
      protocol_version: "1.0",
      request_id: payload.request_id,
      ok: true,
      result: {
        branch: { identifier: "11" },
        evidence_ref: evidenceRef,
      },
    }),
  );

  const result = await tool.execute("call-1", {});

  assert.equal(result.isError, undefined);
  assert.deepEqual(result.details, {
    event: "tool_result",
    capability: "topology.branch.endpoints.get",
    ok: true,
    result: {
      branch: { identifier: "11" },
      evidence_ref: evidenceRef,
    },
    evidence_refs: [evidenceRef],
  });
});

test("rejects mismatched gridctl response correlation", async () => {
  const tool = createGridTool(
    {
      name: "grid_context_open",
      capability: "context.open",
      description: "Open context",
      input_schema: { type: "object", additionalProperties: false, properties: {} },
    },
    async () => ({
      protocol: "grid-capability",
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

test("guide tool rejects traversal and opens published guides", async () => {
  const root = await makeFixtureRoot();
  clearOptionalAnalysisEnvironment();
  const guidePath = join(root, "guides/topology.md");
  const registered = [];
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeFile(guidePath, "# Topology\n\nUse endpoint capability.\n", "utf8");
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root, {
    topology: guidePath,
    escape: join(root, "../outside.md"),
  });

  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });
  const guide = registered.find((tool) => tool.name === "grid_guide_open");

  assert.deepEqual(
    guide.parameters.properties.resource_id.enum,
    ["escape", "topology"],
  );
  assert.match(guide.description, /escape, topology/);

  const opened = await guide.execute("guide-1", { resource_id: "topology" });
  const rejected = await guide.execute("guide-2", { resource_id: "../outside" });
  const escaped = await guide.execute("guide-3", { resource_id: "escape" });

  assert.equal(opened.isError, undefined);
  assert.match(opened.details.result.text, /endpoint capability/);
  assert.equal(rejected.isError, true);
  assert.equal(escaped.isError, true);
});

test("guide tool rejects lexically allowed symlinks outside the published root", async () => {
  const root = await makeFixtureRoot();
  clearOptionalAnalysisEnvironment();
  const outside = await mkdtemp(join(tmpdir(), "grid-domain-tools-outside-"));
  const outsideGuidePath = join(outside, "secret.md");
  const guideSymlinkPath = join(root, "guides/escape.md");
  const registered = [];
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeFile(outsideGuidePath, "outside guide secret", "utf8");
  await symlink(outsideGuidePath, guideSymlinkPath);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root, {
    escape: guideSymlinkPath,
  });

  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });
  const guide = registered.find((tool) => tool.name === "grid_guide_open");

  const result = await guide.execute("guide-escape", { resource_id: "escape" });

  assert.equal(result.isError, true);
  assert.equal(result.details.error.code, "guide_path_rejected");
  assert.doesNotMatch(result.content[0].text, /outside guide secret/);
});

test("guide tool rejects a symlinked parent below the published root", async () => {
  const root = await makeFixtureRoot();
  clearOptionalAnalysisEnvironment();
  const outside = await mkdtemp(join(tmpdir(), "grid-domain-tools-other-run-"));
  const outsideGuidePath = join(outside, "guide.md");
  const linkedParent = join(root, "guides/linked-parent");
  const registered = [];
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeFile(outsideGuidePath, "other run guide", "utf8");
  await symlink(outside, linkedParent);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root, {
    linked: join(linkedParent, "guide.md"),
  });

  domainToolsExtension({ registerTool: (tool) => registered.push(tool) });
  const guide = registered.find((tool) => tool.name === "grid_guide_open");
  const result = await guide.execute("guide-linked-parent", { resource_id: "linked" });

  assert.equal(result.isError, true);
  assert.equal(result.details.error.code, "guide_path_rejected");
  assert.doesNotMatch(result.content[0].text, /other run guide/);
});

test("startup rejects configured symlink paths that escape the workspace", async () => {
  const cases = [
    {
      name: "GRID_AGENT_TOOL_CATALOG",
      link: "tool-catalog-link.json",
      outside: "tool-catalog.json",
      writeOutside: writeCatalog,
    },
    {
      name: "GRID_AGENT_GUIDE_INDEX",
      link: "guide-index-link.json",
      outside: "guide-index.json",
      writeOutside: async (path, root) => writeGuideIndex(path, root),
    },
    {
      name: "GRID_AGENT_ACTIVE_TURN",
      link: "active-turn.json",
      outside: "active-turn.json",
      writeOutside: async (path) => writeFile(path, JSON.stringify({ turn_id: "x", turn_nonce: "n" }), "utf8"),
    },
  ];

  for (const testCase of cases) {
    const root = await makeFixtureRoot();
    const outside = await mkdtemp(join(tmpdir(), "grid-domain-tools-outside-"));
    const outsidePath = join(outside, testCase.outside);
    const linkPath = join(root, "run", testCase.link);
    const registered = [];
    await testCase.writeOutside(outsidePath, root);
    await symlink(outsidePath, linkPath);
    process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
    process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
    process.env.GRID_AGENT_WORKSPACE = join(root, "run");
    await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
    await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);
    process.env[testCase.name] = linkPath;

    assert.throws(
      () => domainToolsExtension({ registerTool: (tool) => registered.push(tool) }),
      new RegExp(`${testCase.name}.*outside GRID_AGENT_WORKSPACE`),
    );
    assert.deepEqual(registered, []);
  }
});

async function makeFixtureRoot() {
  const root = await mkdtemp(join(tmpdir(), "grid-domain-tools-"));
  await mkdir(join(root, "run"), { recursive: true });
  await mkdir(join(root, "guides"), { recursive: true });
  return root;
}

async function configureAnalysisPaths(root, activeTurn, contextView) {
  clearNativeEnvironment();
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  process.env.GRID_AGENT_ACTIVE_TURN = join(root, "run/active-turn.json");
  process.env.GRID_AGENT_ANALYSIS_CONTEXT_VIEW = join(root, "run/context/analysis-context-view.json");
  await mkdir(join(root, "run/context"), { recursive: true });
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);
  await writeFile(process.env.GRID_AGENT_ACTIVE_TURN, JSON.stringify(activeTurn), "utf8");
  await writeFile(process.env.GRID_AGENT_ANALYSIS_CONTEXT_VIEW, JSON.stringify(contextView), "utf8");
}

function clearNativeEnvironment() {
  for (const name of [
    "GRID_AGENT_TRAJECTORY_REQUESTS",
    "GRID_AGENT_TRAJECTORY_CAPTURE_STATE",
    "GRID_AGENT_TRAJECTORY_ALLOWED_REFS",
    "GRID_AGENT_TRAJECTORY_ACKS",
  ]) {
    delete process.env[name];
  }
}

function clearOptionalAnalysisEnvironment() {
  clearNativeEnvironment();
  delete process.env.GRID_AGENT_ACTIVE_TURN;
  delete process.env.GRID_AGENT_ANALYSIS_CONTEXT_VIEW;
}

async function configuredNativeTools() {
  const root = await makeFixtureRoot();
  await configureAnalysisPaths(
    root,
    { turn_id: "analysis-test-t002", turn_nonce: "nonce-2" },
    { schema_version: "analysis-context-view/1.0", revision: 9, state_hash: "sha256:test" },
  );
  process.env.GRID_AGENT_TRAJECTORY_REQUESTS = join(root, "run/requests");
  process.env.GRID_AGENT_TRAJECTORY_CAPTURE_STATE = join(
    root,
    "run/context/trajectory-capture-state.json",
  );
  process.env.GRID_AGENT_TRAJECTORY_ALLOWED_REFS = join(
    root,
    "run/context/trajectory-allowed-refs.json",
  );
  process.env.GRID_AGENT_TRAJECTORY_ACKS = join(root, ".grid-agent/trajectory-acks/analysis-test");
  await mkdir(process.env.GRID_AGENT_TRAJECTORY_REQUESTS, { recursive: true });
  await mkdir(process.env.GRID_AGENT_TRAJECTORY_ACKS, { recursive: true });
  await writeFile(
    process.env.GRID_AGENT_TRAJECTORY_CAPTURE_STATE,
    JSON.stringify({
      source_event_sequences: [1],
      context_revision: 1,
      context_state_hash: "a".repeat(64),
    }),
    "utf8",
  );
  await writeFile(
    process.env.GRID_AGENT_TRAJECTORY_ALLOWED_REFS,
    JSON.stringify({ refs: [] }),
    "utf8",
  );
  const registered = [];
  domainToolsExtension({
    on: () => undefined,
    registerTool: (tool) => registered.push(tool),
  });
  return { registered, root };
}

async function writeCatalog(path, extraTools = []) {
  await writeFile(
    path,
    JSON.stringify({
      protocol: "grid-tool-catalog",
      version: "1.0",
      fingerprint: "sha256:test",
      tools: [
        {
          name: "grid_environment_describe",
          capability: "environment.describe",
          description: "Purpose: describe environment",
          input_schema: { type: "object", additionalProperties: false, properties: {} },
        },
        {
          name: "grid_topology_branch_endpoints",
          capability: "topology.branch.endpoints.get",
          description: "Purpose: endpoints",
          input_schema: {
            type: "object",
            additionalProperties: false,
            required: ["context_ref"],
            properties: { context_ref: { type: "string" } },
          },
        },
        ...extraTools,
      ],
    }),
    "utf8",
  );
}

async function writeGuideIndex(path, root, resources = {}) {
  await writeFile(
    path,
    JSON.stringify({
      protocol: "grid-guide-index",
      version: "1.0",
      root: join(root, "guides"),
      resources,
    }),
    "utf8",
  );
}

async function configureDescriptorAndLegacyPaths(root, descriptorOverrides = {}) {
  const descriptorPath = join(root, "run/pi/domain-runtime.json");
  process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = descriptorPath;
  process.env.GRID_AGENT_TOOL_CATALOG = join(root, "run/tool-catalog.json");
  process.env.GRID_AGENT_GUIDE_INDEX = join(root, "run/guide-index.json");
  process.env.GRID_AGENT_WORKSPACE = join(root, "run");
  await mkdir(join(root, "run/pi"), { recursive: true });
  await writeCatalog(process.env.GRID_AGENT_TOOL_CATALOG);
  await writeGuideIndex(process.env.GRID_AGENT_GUIDE_INDEX, root);
  await writeRuntimeDescriptor(descriptorPath, root, descriptorOverrides);
}

async function writeRuntimeDescriptor(path, root, overrides = {}) {
  await writeFile(
    path,
    JSON.stringify({
      protocol: "grid-capability",
      protocol_version: "1.0",
      executable: "gridctl",
      executable_args: ["request", "--workspace", join(root, "run")],
      tool_name_prefix: "grid_",
      guide_tool_name: "grid_guide_open",
      context_tool_name: "grid_analysis_context_get",
      decision_tool_name: "grid_record_decision",
      tool_catalog_path: join(root, "run/tool-catalog.json"),
      guide_index_path: join(root, "run/guide-index.json"),
      workspace_path: join(root, "run"),
      ...overrides,
    }),
    "utf8",
  );
}
