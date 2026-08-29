import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "@earendil-works/pi-ai";
import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { basename, dirname, isAbsolute, relative, resolve, sep } from "node:path";
import {
  closeSync,
  constants,
  fstatSync,
  lstatSync,
  openSync,
  readFileSync,
  realpathSync,
} from "node:fs";
import { lstat, open, readFile } from "node:fs/promises";

import { configureModelRequestCapture } from "./model-request-capture.mjs";

const { O_DIRECTORY, O_NOFOLLOW, O_RDONLY } = constants;

const LEGACY_DESCRIPTOR_KEYS = new Set([
  "protocol",
  "protocolVersion",
  "executable",
  "executableArgs",
  "toolNamePrefix",
  "guideToolName",
  "contextToolName",
  "decisionToolName",
  "toolCatalogPath",
  "guideIndexPath",
  "guideRootPath",
  "guideIndexSha256",
  "workspacePath",
  "activeTurnPath",
  "analysisContextViewPath",
  "trajectoryRequestsPath",
  "trajectoryCaptureStatePath",
  "trajectoryAllowedRefsPath",
  "trajectoryAcksPath",
  "piRuntime",
]);
const RUNTIME_V1_KEYS = new Set(["schema", "application", "core", "domains"]);
const APPLICATION_KEYS = new Set(["applicationId", "runId", "piRuntime"]);
const CORE_KEYS = new Set([
  "decisionToolName",
  "contextToolName",
  "activeTurnPath",
  "analysisContextViewPath",
  "trajectoryRequestsPath",
  "trajectoryCaptureStatePath",
  "trajectoryAllowedRefsPath",
  "trajectoryAcksPath",
]);
const DOMAIN_KEYS = new Set([
  "bindingId",
  "protocol",
  "protocolVersion",
  "executable",
  "executableArgs",
  "toolCatalogPath",
  "guideToolName",
  "guideIndexPath",
  "guideRootPath",
  "guideIndexSha256",
  "workspacePath",
  "authorityId",
]);
const PROTOCOL_PATTERN = /^[a-z][a-z0-9.-]*$/;
const PROTOCOL_VERSION_PATTERN = /^\d+\.\d+$/;
const BINDING_ID_PATTERN = /^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
const EXECUTABLE_PATTERN = /^[^/\\]+$/;
const TOOL_PREFIX_PATTERN = /^[a-z][a-z0-9_]*_$/;
const TOOL_NAME_PATTERN = /^[a-z][a-z0-9_]*$/;
const RUNTIME_IDENTITY_KEYS = [
  "pi_coding_agent_version",
  "pi_ai_version",
  "pi_source_commit",
  "pi_patch_set_sha256",
];
const RUNTIME_IDENTITY_KEY_SET = new Set(RUNTIME_IDENTITY_KEYS);
const CANONICAL_SECRET_NAMES = [
  "OPENAI_API_KEY",
  "OPENROUTER_API_KEY",
  "DEEPSEEK_API_KEY",
  "MINIMAX_API_KEY",
];
const RESOURCE_ID_PATTERN = /^[a-z0-9][a-z0-9-]+$/;
const ENCODED_SEPARATOR_PATTERN = /%(?:2f|5c)/i;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const DEFAULT_TRANSPORT_LIMITS = Object.freeze({
  timeoutMs: 60_000,
  maxOutputBytes: 1_048_576,
});
const MAX_TRANSPORT_LIMITS = Object.freeze({
  timeoutMs: 120_000,
  maxOutputBytes: 4_194_304,
});
const LEGACY_RUNTIME_DESCRIPTORS = new WeakSet();
const SELECTED_BINDING_RUNTIMES = new WeakSet();
const LEGACY_SELECTED_BINDING_RUNTIMES = new WeakSet();
const MODEL_ROUTING_FIELDS = new Set([
  "binding",
  "bindingid",
  "executable",
  "executableargs",
  "protocol",
  "version",
  "protocolversion",
  "authority",
  "authorityid",
  "workspace",
  "workspacepath",
  "toolcatalogpath",
  "toolcatalog",
  "catalogpath",
  "catalog",
  "guidetoolname",
  "guidetool",
  "guideindexpath",
  "guideindex",
  "guiderootpath",
  "guideroot",
  "guideindexsha256",
  "guidedigest",
  "contexttoolname",
  "contexttool",
  "decisiontoolname",
  "decisiontool",
  "activeturnpath",
  "analysiscontextviewpath",
  "trajectoryrequestspath",
  "trajectorycapturestatepath",
  "trajectoryallowedrefspath",
  "trajectoryackspath",
  "args",
  "arguments",
  "endpoint",
  "endpointpath",
  "command",
  "commandargs",
  "toolnameprefix",
]);

/**
 * Validate and detach the controller-owned runtime descriptor.
 *
 * Pi receives only the returned immutable copy. In particular, the process
 * executable and argument template can never be supplied by tool input.
 */
export function validateRuntimeDescriptor(value) {
  if (LEGACY_RUNTIME_DESCRIPTORS.has(value)) {
    return value;
  }
  if (isPlainObject(value) && value.schema !== undefined) {
    return validateRuntimeV1(value);
  }
  return legacyDescriptorToRuntimeV1(value);
}

export function legacyDescriptorToRuntimeV1(value) {
  const legacy = validateLegacyRuntimeDescriptor(value);
  const bindingId = legacy.toolNamePrefix.slice(0, -1).replaceAll("_", "-");
  if (!BINDING_ID_PATTERN.test(bindingId)) {
    throw new TypeError("legacy runtime descriptor toolNamePrefix cannot form a bindingId");
  }
  const core = compactObject({
    decisionToolName: legacy.decisionToolName,
    contextToolName: legacy.contextToolName,
    activeTurnPath: legacy.activeTurnPath,
    analysisContextViewPath: legacy.analysisContextViewPath,
    trajectoryRequestsPath: legacy.trajectoryRequestsPath,
    trajectoryCaptureStatePath: legacy.trajectoryCaptureStatePath,
    trajectoryAllowedRefsPath: legacy.trajectoryAllowedRefsPath,
    trajectoryAcksPath: legacy.trajectoryAcksPath,
  });
  const domain = compactObject({
    bindingId,
    protocol: legacy.protocol,
    protocolVersion: legacy.protocolVersion,
    executable: legacy.executable,
    executableArgs: legacy.executableArgs,
    toolCatalogPath: legacy.toolCatalogPath,
    guideToolName: legacy.guideToolName,
    guideIndexPath: legacy.guideIndexPath,
    guideRootPath: legacy.guideRootPath,
    guideIndexSha256: legacy.guideIndexSha256,
    workspacePath: legacy.workspacePath,
    authorityId: legacy.executable,
  });
  const runtime = validateRuntimeV1(
    {
      schema: "capability-agent-runtime/1.0",
      application: compactObject({
        applicationId: "legacy-capability-agent",
        runId: "legacy-run",
        piRuntime: legacy.piRuntime,
      }),
      core,
      domains: [domain],
    },
    { legacy: true },
  );
  LEGACY_RUNTIME_DESCRIPTORS.add(runtime);
  return runtime;
}

function validateLegacyRuntimeDescriptor(value) {
  if (!isPlainObject(value)) {
    throw new TypeError("runtime descriptor must be a plain object");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || !LEGACY_DESCRIPTOR_KEYS.has(key)) {
      throw new TypeError(`runtime descriptor contains an unknown field: ${String(key)}`);
    }
  }

  const descriptor = {
    protocol: requirePattern(value.protocol, "protocol", PROTOCOL_PATTERN),
    protocolVersion: requirePattern(value.protocolVersion, "protocolVersion", PROTOCOL_VERSION_PATTERN),
    executable: requireExecutable(value.executable),
    executableArgs: requireStringArray(value.executableArgs, "executableArgs"),
    toolNamePrefix: requirePattern(value.toolNamePrefix, "toolNamePrefix", TOOL_PREFIX_PATTERN),
    guideToolName: requireBoundedToolName(value.guideToolName, "guideToolName", value.toolNamePrefix),
    contextToolName: requireBoundedToolName(
      value.contextToolName,
      "contextToolName",
      value.toolNamePrefix,
    ),
    decisionToolName: requireBoundedToolName(
      value.decisionToolName,
      "decisionToolName",
      value.toolNamePrefix,
    ),
  };

  for (const key of [
    "toolCatalogPath",
    "guideIndexPath",
    "workspacePath",
    "activeTurnPath",
    "analysisContextViewPath",
    "trajectoryRequestsPath",
    "trajectoryCaptureStatePath",
    "trajectoryAllowedRefsPath",
    "trajectoryAcksPath",
    "guideRootPath",
  ]) {
    if (value[key] !== undefined) {
      descriptor[key] = requireAbsolutePath(value[key], key);
    }
  }
  if (value.guideIndexSha256 !== undefined) {
    descriptor.guideIndexSha256 = requirePattern(
      value.guideIndexSha256,
      "guideIndexSha256",
      SHA256_PATTERN,
    );
  }
  if (value.piRuntime !== undefined) {
    descriptor.piRuntime = cloneRuntime(value.piRuntime);
  }

  descriptor.executableArgs = Object.freeze([...descriptor.executableArgs]);
  return Object.freeze(descriptor);
}

function validateRuntimeV1(value, options = {}) {
  requireExactKeys(value, RUNTIME_V1_KEYS, "runtime descriptor");
  if (value.schema !== "capability-agent-runtime/1.0") {
    throw new TypeError("runtime descriptor schema is invalid");
  }
  requireExactKeys(value.application, APPLICATION_KEYS, "runtime descriptor application", {
    required: ["applicationId", "runId"],
  });
  const application = {
    applicationId: requireNonEmptyString(value.application.applicationId, "applicationId"),
    runId: requireNonEmptyString(value.application.runId, "runId"),
  };
  if (value.application.piRuntime !== undefined) {
    application.piRuntime = cloneRuntime(value.application.piRuntime);
  }

  requireExactKeys(value.core, CORE_KEYS, "runtime descriptor core", {
    required: ["decisionToolName", "contextToolName"],
  });
  const core = {
    decisionToolName: requirePattern(
      value.core.decisionToolName,
      "core decisionToolName",
      TOOL_NAME_PATTERN,
    ),
    contextToolName: requirePattern(
      value.core.contextToolName,
      "core contextToolName",
      TOOL_NAME_PATTERN,
    ),
  };
  if (
    !options.legacy &&
    (
      !core.decisionToolName.startsWith("agent_") ||
      !core.contextToolName.startsWith("agent_") ||
      core.decisionToolName === core.contextToolName
    )
  ) {
    throw new TypeError("runtime descriptor core tool names must be distinct agent_* names");
  }
  for (const key of [
    "activeTurnPath",
    "analysisContextViewPath",
    "trajectoryRequestsPath",
    "trajectoryCaptureStatePath",
    "trajectoryAllowedRefsPath",
    "trajectoryAcksPath",
  ]) {
    if (value.core[key] !== undefined) {
      core[key] = requireAbsolutePath(value.core[key], `core ${key}`);
    }
  }

  if (!Array.isArray(value.domains) || value.domains.length !== 1) {
    throw new TypeError("runtime descriptor requires exactly one domain binding");
  }
  const domain = validateRuntimeDomain(value.domains[0], options);
  const routingToolNames = [
    core.decisionToolName,
    core.contextToolName,
    domain.guideToolName,
  ];
  if (new Set(routingToolNames).size !== routingToolNames.length) {
    throw new TypeError("runtime descriptor tool name collision");
  }
  if (!options.legacy) {
    if (domain.guideToolName.startsWith("agent_")) {
      throw new TypeError("runtime descriptor agent_ namespace is reserved for core tools");
    }
    for (const [key, candidate] of Object.entries(core)) {
      if (key.endsWith("Path")) {
        requireInside(candidate, domain.workspacePath, key);
      }
    }
  }
  const runtime = Object.freeze({
    schema: value.schema,
    application: Object.freeze(application),
    core: Object.freeze(core),
    domains: Object.freeze([domain]),
  });
  return runtime;
}

function validateRuntimeDomain(value, { legacy = false } = {}) {
  requireExactKeys(value, DOMAIN_KEYS, "runtime descriptor domain", {
    required: legacy
      ? [
          "bindingId",
          "protocol",
          "protocolVersion",
          "executable",
          "executableArgs",
          "guideToolName",
          "authorityId",
        ]
      : [...DOMAIN_KEYS],
  });
  const bindingId = requirePattern(value.bindingId, "domain bindingId", BINDING_ID_PATTERN);
  const protocol = requirePattern(value.protocol, "domain protocol", PROTOCOL_PATTERN);
  const protocolVersion = requirePattern(
    value.protocolVersion,
    "domain protocolVersion",
    PROTOCOL_VERSION_PATTERN,
  );
  const executable = requireExecutable(value.executable);
  const executableArgs = Object.freeze([
    ...requireStringArray(value.executableArgs, "domain executableArgs"),
  ]);
  const guideToolName = requirePattern(
    value.guideToolName,
    "domain guideToolName",
    TOOL_NAME_PATTERN,
  );
  const toolNamePrefix = toolPrefixFromGuideName(guideToolName);
  const authorityId = requirePattern(value.authorityId, "domain authorityId", PROTOCOL_PATTERN);
  const domain = {
    bindingId,
    protocol,
    protocolVersion,
    executable,
    executableArgs,
    guideToolName: requireBoundedToolName(
      guideToolName,
      "domain guideToolName",
      toolNamePrefix,
    ),
    authorityId,
  };
  const pathFields = ["workspacePath", "toolCatalogPath", "guideIndexPath", "guideRootPath"];
  for (const key of pathFields) {
    if (value[key] !== undefined) {
      domain[key] = requireAbsolutePath(value[key], `domain ${key}`);
    }
  }
  if (!legacy) {
    const workspacePath = domain.workspacePath;
    if (workspacePath === undefined) {
      throw new TypeError("runtime descriptor domain workspacePath is required");
    }
    for (const key of ["toolCatalogPath", "guideIndexPath", "guideRootPath"]) {
      if (domain[key] !== undefined && (!legacy || key !== "guideRootPath")) {
        requireInside(domain[key], workspacePath, key);
      }
    }
    for (const argument of executableArgs) {
      if (isAbsolute(argument) && !isInside(resolve(argument), workspacePath)) {
        throw new TypeError(
          "runtime descriptor domain executableArgs path is outside workspacePath",
        );
      }
    }
  }
  if (value.guideIndexSha256 !== undefined) {
    domain.guideIndexSha256 = requirePattern(
      value.guideIndexSha256,
      "domain guideIndexSha256",
      SHA256_PATTERN,
    );
  }
  return Object.freeze(domain);
}

export function buildCapabilityRequest(descriptor, capability, params, requestId = randomUUID()) {
  const runtime = selectedBindingRuntime(descriptor);
  if (typeof capability !== "string" || capability.length === 0) {
    throw new TypeError("capability must be a non-empty string");
  }
  if (typeof requestId !== "string" || requestId.length === 0) {
    throw new TypeError("requestId must be a non-empty string");
  }
  if (!isPlainObject(params)) {
    throw new TypeError("capability arguments must be a plain object");
  }
  for (const key of Reflect.ownKeys(params)) {
    if (
      typeof key !== "string" ||
      MODEL_ROUTING_FIELDS.has(key.replaceAll(/[-_]/g, "").toLowerCase())
    ) {
      throw new TypeError(`capability arguments contain a controller-owned routing field: ${String(key)}`);
    }
  }
  return {
    protocol: runtime.protocol,
    protocol_version: runtime.protocolVersion,
    request_id: requestId,
    capability,
    arguments: params,
  };
}

export function createCapabilityTool(descriptor, contract, runner) {
  const runtime = selectedBindingRuntime(descriptor);
  validateContract(contract, runtime);
  const executeRunner = runner ?? ((payload) => runCapability(payload, runtime));
  return defineTool({
    name: contract.name,
    label: contract.name,
    description: contract.description,
    parameters: Type.Unsafe(contract.input_schema),
    async execute(_id, params) {
      const payload = buildCapabilityRequest(runtime, contract.capability, params);
      const response = await executeRunner(payload);
      if (!isCorrelatedResponse(response, payload.request_id, runtime)) {
        return toolError(
          {
            code: "response_correlation_mismatch",
            phase: "parse",
            message: "capability response did not match the request id",
            details: { expected_request_id: payload.request_id, response },
          },
          contract.capability,
        );
      }
      if (response.ok !== true) {
        const details = canonicalToolResult(contract.capability, response);
        return {
          content: [{ type: "text", text: JSON.stringify(response) }],
          details,
          isError: true,
        };
      }
      return {
        content: [{ type: "text", text: JSON.stringify(response) }],
        details: canonicalToolResult(contract.capability, response),
      };
    },
  });
}

/**
 * Materialize the generic extension after the controller has selected a
 * descriptor. The returned callback is compatible with Pi's extension API.
 */
export function createDomainToolsExtension(descriptor, options = {}) {
  const runtime = selectedBindingRuntime(descriptor);
  if (
    !isPlainObject(options) ||
    (options.createTool !== undefined && typeof options.createTool !== "function") ||
    (options.modelRequestSchemaVersion !== undefined &&
      typeof options.modelRequestSchemaVersion !== "string") ||
    (options.selectedSecretNames !== undefined &&
      (!Array.isArray(options.selectedSecretNames) ||
        !options.selectedSecretNames.every((name) => typeof name === "string" && name.length > 0)))
  ) {
    throw new TypeError(
      "domain tools extension options must provide a createTool function and selected secret names",
    );
  }
  const buildTool = options.createTool ?? createCapabilityTool;
  const selectedNames = Object.freeze([...(options.selectedSecretNames ?? [])]);
  return function domainToolsExtension(pi) {
    const paths = runtimePaths(runtime);
    const catalog = readJsonSync(paths.toolCatalogPath);
    if (!Array.isArray(catalog.tools)) {
      throw new Error("tool catalog must contain a tools array");
    }
    preflightContracts(catalog.tools, runtime);
    if (
      paths.trajectoryRequestsPath !== undefined &&
      paths.trajectoryCaptureStatePath !== undefined &&
      paths.trajectoryAllowedRefsPath !== undefined &&
      paths.trajectoryAcksPath !== undefined
    ) {
      configureModelRequestCapture(pi, {
        requestsPath: paths.trajectoryRequestsPath,
        activeTurnPath: paths.activeTurnPath,
        captureStatePath: paths.trajectoryCaptureStatePath,
        allowedRefsPath: paths.trajectoryAllowedRefsPath,
        acknowledgementsPath: paths.trajectoryAcksPath,
        runtime: paths.piRuntime,
        schemaVersion: options.modelRequestSchemaVersion,
      });
    }
    for (const contract of catalog.tools) {
      if (contract.name === runtime.decisionToolName) {
        continue;
      }
      pi.registerTool(
        buildTool(runtime, contract, (payload) => runCapability(payload, runtime, selectedNames)),
      );
    }
    pi.registerTool(
      createGuideTool(
        runtime,
        paths.guideIndexPath,
        paths.guideWorkspacePath,
        paths.guideRootPath,
        paths.guideIndexSha256,
      ),
    );
    if (paths.analysisContextViewPath !== undefined) {
      pi.registerTool(createAnalysisContextTool(runtime.contextToolName, paths.analysisContextViewPath));
    }
    if (paths.trajectoryAllowedRefsPath !== undefined && paths.activeTurnPath !== undefined) {
      pi.registerTool(
        createRecordDecisionTool(runtime.decisionToolName, paths.trajectoryAllowedRefsPath, paths.activeTurnPath),
      );
    }
  };
}

function preflightContracts(contracts, runtime) {
  const names = new Set([
    runtime.guideToolName,
    runtime.contextToolName,
    runtime.decisionToolName,
  ]);
  const legacy = LEGACY_SELECTED_BINDING_RUNTIMES.has(runtime);
  let legacyDecisionAliases = 0;
  for (const contract of contracts) {
    if (
      legacy &&
      isPlainObject(contract) &&
      contract.name === runtime.decisionToolName
    ) {
      legacyDecisionAliases += 1;
      if (legacyDecisionAliases > 1) {
        throw new TypeError("runtime descriptor tool name collision");
      }
      continue;
    }
    if (
      !isPlainObject(contract) ||
      typeof contract.name !== "string" ||
      names.has(contract.name) ||
      (!legacy && contract.name.startsWith("agent_"))
    ) {
      throw new TypeError("runtime descriptor tool name collision");
    }
    names.add(contract.name);
  }
  for (const contract of contracts) {
    if (!(legacy && contract.name === runtime.decisionToolName)) {
      validateContract(contract, runtime);
    }
  }
}

export function sanitizeEnvironment(env, selectedNames = []) {
  const blocked = new Set([
    ...CANONICAL_SECRET_NAMES,
    ...selectedNames,
    "CAPABILITY_AGENT_SECRET_ENV_NAMES",
  ]);
  return Object.fromEntries(
    Object.entries(env).filter(([name]) => !blocked.has(name) && !isCredentialName(name)),
  );
}

export function runCapability(payload, descriptor, selectedNames = [], transportLimits = undefined) {
  const runtime = selectedBindingRuntime(descriptor);
  validateExecutableArgumentPaths(runtime);
  const limits = validateTransportLimits(transportLimits);
  return new Promise((resolveResponse) => {
    const child = spawn(runtime.executable, runtime.executableArgs, {
      env: sanitizeEnvironment(process.env, [...selectedSecretNames(process.env), ...selectedNames]),
      stdio: ["pipe", "pipe", "pipe"],
    });
    const stdout = [];
    const stderr = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let settled = false;
    const finish = (response) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      resolveResponse(response);
    };
    const stopWithError = (code, message) => {
      child.kill("SIGKILL");
      finish(transportError(payload.request_id, runtime, message, code));
    };
    const timer = setTimeout(() => {
      stopWithError(
        "capability_transport_timeout",
        `capability executable exceeded ${limits.timeoutMs}ms transport timeout`,
      );
    }, limits.timeoutMs);
    child.stdout.on("data", (chunk) => {
      const buffer = Buffer.from(chunk);
      stdoutBytes += buffer.byteLength;
      if (stdoutBytes + stderrBytes > limits.maxOutputBytes) {
        stopWithError(
          "capability_transport_output_limit",
          `capability executable exceeded ${limits.maxOutputBytes} transport output bytes`,
        );
        return;
      }
      stdout.push(buffer);
    });
    child.stderr.on("data", (chunk) => {
      const buffer = Buffer.from(chunk);
      stderrBytes += buffer.byteLength;
      if (stdoutBytes + stderrBytes > limits.maxOutputBytes) {
        stopWithError(
          "capability_transport_output_limit",
          `capability executable exceeded ${limits.maxOutputBytes} transport output bytes`,
        );
        return;
      }
      stderr.push(buffer);
    });
    child.on("error", (error) => {
      finish(transportError(payload.request_id, runtime, error.message));
    });
    child.on("close", () => {
      if (settled) {
        return;
      }
      const stdoutText = Buffer.concat(stdout).toString("utf8");
      const stderrText = Buffer.concat(stderr).toString("utf8");
      try {
        finish(JSON.parse(stdoutText));
      } catch {
        finish(
          transportError(
            payload.request_id,
            runtime,
            stderrText || stdoutText || "capability executable returned no JSON",
          ),
        );
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

function validateExecutableArgumentPaths(runtime) {
  const absoluteArguments = runtime.executableArgs.filter((argument) => isAbsolute(argument));
  if (absoluteArguments.length === 0) {
    return;
  }
  const workspaceValue = runtime.workspacePath ?? workspaceArgument(runtime.executableArgs);
  if (workspaceValue === undefined) {
    throw new TypeError(
      "runtime descriptor executableArgs absolute paths require workspacePath",
    );
  }
  const workspacePath = requiredExistingRealPath(workspaceValue, "workspacePath");
  for (const argument of absoluteArguments) {
    let candidate;
    try {
      candidate = realpathSync(argument);
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw new TypeError(
          `runtime descriptor executableArgs path is unavailable: ${error.message}`,
        );
      }
      candidate = requiredWritableRealPath(argument, "executableArgs");
    }
    if (!isInside(candidate, workspacePath)) {
      throw new TypeError(
        "runtime descriptor executableArgs path is outside workspacePath",
      );
    }
  }
}

function workspaceArgument(executableArgs) {
  const index = executableArgs.indexOf("--workspace");
  const candidate = index < 0 ? undefined : executableArgs[index + 1];
  return typeof candidate === "string" && isAbsolute(candidate) ? candidate : undefined;
}

function validateTransportLimits(value) {
  if (value === undefined) {
    return DEFAULT_TRANSPORT_LIMITS;
  }
  if (!isPlainObject(value)) {
    throw new TypeError("transport limits must be a plain object");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (key !== "timeoutMs" && key !== "maxOutputBytes") {
      throw new TypeError(`transport limits contain an unknown field: ${String(key)}`);
    }
  }
  const limits = {};
  for (const key of ["timeoutMs", "maxOutputBytes"]) {
    const selected = value[key] ?? DEFAULT_TRANSPORT_LIMITS[key];
    if (!Number.isSafeInteger(selected) || selected < 1 || selected > MAX_TRANSPORT_LIMITS[key]) {
      throw new TypeError(`transport limit ${key} must be between 1 and ${MAX_TRANSPORT_LIMITS[key]}`);
    }
    limits[key] = selected;
  }
  return Object.freeze(limits);
}

function createGuideTool(
  descriptor,
  guideIndexPath,
  guideWorkspacePath,
  descriptorGuideRoot,
  descriptorGuideDigest,
) {
  const startupRead = readBoundFileSync(guideWorkspacePath, guideIndexPath);
  if (
    descriptorGuideDigest !== undefined &&
    startupRead.sha256 !== descriptorGuideDigest
  ) {
    throw new Error("guide index digest does not match the runtime descriptor");
  }
  const expectedRoot = descriptorGuideRoot ?? resolve(String(JSON.parse(startupRead.text).root));
  const guideIndex = validateGuideIndex(
    JSON.parse(startupRead.text),
    descriptor,
    expectedRoot,
  );
  const startupRootIdentity = readBoundDirectorySync(expectedRoot, "guide root");
  const resourceIds = Object.keys(guideIndex.resources ?? {}).sort();
  const resourceIdSchema = {
    type: "string",
    description: `Published resource ids: ${resourceIds.join(", ") || "none"}.`,
  };
  if (resourceIds.length > 0) {
    resourceIdSchema.enum = resourceIds;
  } else {
    resourceIdSchema.pattern = "a^";
  }
  return defineTool({
    name: descriptor.guideToolName,
    label: descriptor.guideToolName,
    description: `Open a published analysis guide by resource id. Published ids: ${resourceIds.join(", ") || "none"}.`,
    parameters: Type.Unsafe({
      type: "object",
      additionalProperties: false,
      required: ["resource_id"],
      properties: { resource_id: resourceIdSchema },
    }),
    async execute(_id, params) {
      if (
        !RESOURCE_ID_PATTERN.test(params.resource_id) ||
        ENCODED_SEPARATOR_PATTERN.test(params.resource_id)
      ) {
        return toolError(
          {
            code: "guide_not_found",
            phase: "resolve",
            message: "guide resource is not published",
          },
          descriptor.guideToolName,
        );
      }
      try {
        const currentRead = await readBoundFile(guideWorkspacePath, guideIndexPath);
        if (
          currentRead.sha256 !== startupRead.sha256 ||
          currentRead.identity !== startupRead.identity
        ) {
          throw new Error("guide index named binding changed after startup");
        }
        const currentIndex = validateGuideIndex(
          JSON.parse(currentRead.text),
          descriptor,
          expectedRoot,
        );
        const resourcePath = currentIndex.resources[params.resource_id];
        if (typeof resourcePath !== "string") {
          return toolError(
            {
              code: "guide_not_found",
              phase: "resolve",
              message: "guide resource is not published",
            },
            descriptor.guideToolName,
          );
        }
        const guide = await readPublishedFile(expectedRoot, resourcePath);
        if (guide.rootIdentity !== startupRootIdentity) {
          throw new Error("guide root named binding changed after startup");
        }
        const text = guide.text;
        const result = { resource_id: params.resource_id, text };
        return {
          content: [{ type: "text", text }],
          details: {
            event: "tool_result",
            capability: descriptor.guideToolName,
            ok: true,
            result,
            evidence_refs: [],
          },
        };
      } catch {
        return toolError(
          {
            code: "guide_path_rejected",
            phase: "resolve",
            message: "guide resource path is unavailable",
          },
          descriptor.guideToolName,
        );
      }
    },
  });
}

function readBoundDirectorySync(path, label) {
  const descriptor = openSync(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
  try {
    const opened = fstatSync(descriptor, { bigint: true });
    const named = lstatSync(path, { bigint: true });
    if (
      !opened.isDirectory() ||
      !named.isDirectory() ||
      named.dev !== opened.dev ||
      named.ino !== opened.ino
    ) {
      throw new Error(`${label} named binding is invalid`);
    }
    return statIdentity(opened);
  } finally {
    closeSync(descriptor);
  }
}

function validateGuideIndex(value, descriptor, expectedRoot) {
  if (!isPlainObject(value)) {
    throw new Error("guide index must be an object");
  }
  const keys = new Set(["protocol", "version", "root", "resources"]);
  if (Reflect.ownKeys(value).some((key) => typeof key !== "string" || !keys.has(key))) {
    throw new Error("guide index contains an unknown field");
  }
  const expectedProtocol = `${descriptor.protocol.split("-", 1)[0]}-guide-index`;
  if (value.protocol !== expectedProtocol || value.version !== "1.0") {
    throw new Error("guide index protocol or version is invalid");
  }
  if (
    typeof value.root !== "string" ||
    !isAbsolute(value.root) ||
    resolve(value.root) !== expectedRoot
  ) {
    throw new Error("guide index root does not match the runtime descriptor");
  }
  if (!isPlainObject(value.resources)) {
    throw new Error("guide index resources must be an object");
  }
  const resources = {};
  for (const [resourceId, resourcePath] of Object.entries(value.resources)) {
    const candidate = typeof resourcePath === "string" ? resolve(resourcePath) : "";
    if (
      !RESOURCE_ID_PATTERN.test(resourceId) ||
      ENCODED_SEPARATOR_PATTERN.test(resourceId) ||
      typeof resourcePath !== "string" ||
      !isAbsolute(resourcePath) ||
      candidate !== resourcePath ||
      candidate === expectedRoot ||
      !isInside(candidate, expectedRoot)
    ) {
      throw new Error("guide index resource mapping is invalid");
    }
    resources[resourceId] = resourcePath;
  }
  return Object.freeze({
    protocol: value.protocol,
    version: value.version,
    root: expectedRoot,
    resources: Object.freeze(resources),
  });
}

function readBoundFileSync(rootPath, filePath) {
  const root = resolve(rootPath);
  const candidate = resolve(filePath);
  const segments = safeRelativeSegments(root, candidate, "guide index");
  const handles = [];
  const bindings = [];
  try {
    const rootDescriptor = openSync(root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    handles.push(rootDescriptor);
    bindings.push({ path: root, descriptor: rootDescriptor, directory: true });
    let currentPath = root;
    for (const segment of segments.slice(0, -1)) {
      currentPath = resolve(currentPath, segment);
      const descriptor = openSync(
        currentPath,
        O_RDONLY | O_DIRECTORY | O_NOFOLLOW,
      );
      handles.push(descriptor);
      bindings.push({ path: currentPath, descriptor, directory: true });
    }
    const descriptor = openSync(candidate, O_RDONLY | O_NOFOLLOW);
    handles.push(descriptor);
    bindings.push({ path: candidate, descriptor, directory: false });
    const before = fstatSync(descriptor, { bigint: true });
    if (!before.isFile()) {
      throw new Error("guide index is not a regular file");
    }
    const content = readFileSync(descriptor);
    const after = fstatSync(descriptor, { bigint: true });
    verifySyncBindings(bindings);
    if (statIdentity(before) !== statIdentity(after)) {
      throw new Error("guide index changed while reading");
    }
    return {
      text: content.toString("utf8"),
      sha256: createHash("sha256").update(content).digest("hex"),
      identity: statIdentity(after),
    };
  } finally {
    for (const descriptor of handles.reverse()) {
      closeSync(descriptor);
    }
  }
}

function verifySyncBindings(bindings) {
  for (const binding of bindings) {
    const named = lstatSync(binding.path, { bigint: true });
    const opened = fstatSync(binding.descriptor, { bigint: true });
    if (
      (binding.directory ? !named.isDirectory() : !named.isFile()) ||
      named.dev !== opened.dev ||
      named.ino !== opened.ino
    ) {
      throw new Error("guide index named binding changed while reading");
    }
  }
}

async function readBoundFile(rootPath, filePath) {
  const root = resolve(rootPath);
  const candidate = resolve(filePath);
  const segments = safeRelativeSegments(root, candidate, "published file");
  const handles = [];
  const bindings = [];
  try {
    const rootHandle = await open(root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    handles.push(rootHandle);
    bindings.push({ path: root, handle: rootHandle, directory: true });
    let currentPath = root;
    for (const segment of segments.slice(0, -1)) {
      currentPath = resolve(currentPath, segment);
      const handle = await open(currentPath, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
      handles.push(handle);
      bindings.push({ path: currentPath, handle, directory: true });
    }
    const handle = await open(candidate, O_RDONLY | O_NOFOLLOW);
    handles.push(handle);
    bindings.push({ path: candidate, handle, directory: false });
    const before = await handle.stat({ bigint: true });
    if (!before.isFile()) {
      throw new Error("published file is not a regular file");
    }
    const content = await handle.readFile();
    const after = await handle.stat({ bigint: true });
    for (const binding of bindings) {
      const named = await lstat(binding.path, { bigint: true });
      const opened = await binding.handle.stat({ bigint: true });
      if (
        (binding.directory ? !named.isDirectory() : !named.isFile()) ||
        named.dev !== opened.dev ||
        named.ino !== opened.ino
      ) {
        throw new Error("published file named binding changed while reading");
      }
    }
    if (statIdentity(before) !== statIdentity(after)) {
      throw new Error("published file changed while reading");
    }
    return {
      text: content.toString("utf8"),
      sha256: createHash("sha256").update(content).digest("hex"),
      identity: statIdentity(after),
      rootIdentity: statIdentity(await bindings[0].handle.stat({ bigint: true })),
    };
  } finally {
    for (const handle of handles.reverse()) {
      await handle.close().catch(() => undefined);
    }
  }
}

function safeRelativeSegments(root, candidate, label) {
  if (!isInside(candidate, root) || candidate === root) {
    throw new Error(`${label} is outside its trusted root`);
  }
  const segments = relative(root, candidate).split(sep);
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    throw new Error(`${label} has an unsafe path segment`);
  }
  return segments;
}

async function readPublishedFile(rootPath, resourcePath) {
  const root = resolve(rootPath);
  const candidate = resolve(resourcePath);
  safeRelativeSegments(root, candidate, "published resource");
  return readBoundFile(root, candidate);
}

function statIdentity(value) {
  return [
    value.dev,
    value.ino,
    value.size,
    value.mode,
    value.mtimeNs,
    value.ctimeNs,
  ].join(":");
}

function createAnalysisContextTool(toolName, analysisContextViewPath) {
  return defineTool({
    name: toolName,
    label: toolName,
    description: "Return the controller-generated bounded read-only analysis context view.",
    parameters: Type.Object({}),
    async execute() {
      const result = await readJson(analysisContextViewPath);
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details: {
          event: "tool_result",
          capability: toolName,
          ok: true,
          result,
          evidence_refs: [],
        },
      };
    },
  });
}

function createRecordDecisionTool(toolName, allowedRefsPath, activeTurnPath) {
  return defineTool({
    name: toolName,
    label: toolName,
    description: "Declare bounded agent intent. This is not simulator truth and creates no evidence.",
    parameters: Type.Object(
      {
        intent: Type.String({ minLength: 1, maxLength: 500 }),
        decision: Type.String({ minLength: 1, maxLength: 500 }),
        next_action: Type.String({ minLength: 1, maxLength: 500 }),
        refs: Type.Array(Type.String({ minLength: 1 }), { maxItems: 20 }),
      },
      { additionalProperties: false },
    ),
    async execute(_id, params) {
      const invalid = decisionValidationError(params);
      if (invalid !== undefined) {
        return toolError(
          { code: "invalid_decision", phase: "validate", message: invalid },
          toolName,
        );
      }
      await readActiveTurn(activeTurnPath);
      let known;
      try {
        known = await readAllowedRefs(allowedRefsPath);
      } catch (error) {
        return toolError(
          {
            code: "decision_state_invalid",
            phase: "resolve",
            message: error instanceof Error ? error.message : String(error),
          },
          toolName,
        );
      }
      if (params.refs.some((reference) => !known.has(reference))) {
        return toolError(
          {
            code: "unknown_decision_ref",
            phase: "resolve",
            message: "decision refs must be known in the current run",
          },
          toolName,
        );
      }
      const result = {
        intent: params.intent,
        decision: params.decision,
        next_action: params.next_action,
        refs: [...params.refs],
      };
      const details = {
        event: "tool_result",
        capability: toolName,
        ok: true,
        result,
        evidence_refs: [],
      };
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        details,
      };
    },
  });
}

function runtimePaths(descriptor) {
  const legacy = LEGACY_SELECTED_BINDING_RUNTIMES.has(descriptor);
  const workspacePath = requiredExistingRealPath(descriptor.workspacePath, "workspacePath");
  const toolCatalogPath = requiredExistingRealPath(descriptor.toolCatalogPath, "toolCatalogPath");
  const guideWorkspacePath = legacy ? resolve(descriptor.workspacePath) : workspacePath;
  const guideIndexPath = legacy
    ? resolve(descriptor.guideIndexPath)
    : requiredExistingRealPath(descriptor.guideIndexPath, "guideIndexPath");
  const guideRootPath = descriptor.guideRootPath === undefined
    ? undefined
    : legacy
      ? resolve(descriptor.guideRootPath)
      : requiredExistingRealPath(descriptor.guideRootPath, "guideRootPath");
  const activeTurnPath = optionalWritableRealPath(descriptor.activeTurnPath, "activeTurnPath");
  const analysisContextViewPath = optionalExistingRealPath(
    descriptor.analysisContextViewPath,
    "analysisContextViewPath",
  );
  const trajectoryRequestsPath = optionalExistingRealPath(
    descriptor.trajectoryRequestsPath,
    "trajectoryRequestsPath",
  );
  const trajectoryCaptureStatePath = optionalExistingRealPath(
    descriptor.trajectoryCaptureStatePath,
    "trajectoryCaptureStatePath",
  );
  const trajectoryAllowedRefsPath = optionalExistingRealPath(
    descriptor.trajectoryAllowedRefsPath,
    "trajectoryAllowedRefsPath",
  );
  const trajectoryAcksPath = optionalExistingRealPath(descriptor.trajectoryAcksPath, "trajectoryAcksPath");
  const trajectoryPaths = [
    trajectoryRequestsPath,
    trajectoryCaptureStatePath,
    trajectoryAllowedRefsPath,
    trajectoryAcksPath,
  ];
  const trajectoryConfigured = trajectoryPaths.every((path) => path !== undefined);
  if (trajectoryPaths.some((path) => path !== undefined) && !trajectoryConfigured) {
    throw new Error("trajectory capture requires all four trajectory paths");
  }
  if (trajectoryConfigured && activeTurnPath === undefined) {
    throw new Error("trajectory capture requires activeTurnPath");
  }
  const corePathBindings = [
    ["toolCatalogPath", toolCatalogPath],
    ["activeTurnPath", activeTurnPath],
    ["analysisContextViewPath", analysisContextViewPath],
    ["trajectoryRequestsPath", trajectoryRequestsPath],
    ["trajectoryCaptureStatePath", trajectoryCaptureStatePath],
    ["trajectoryAllowedRefsPath", trajectoryAllowedRefsPath],
  ];
  if (!legacy) {
    corePathBindings.push(
      ["trajectoryAcksPath", trajectoryAcksPath],
      ["guideRootPath", guideRootPath],
    );
  }
  for (const [name, candidate] of corePathBindings) {
    if (candidate !== undefined && !isInside(candidate, workspacePath)) {
      throw new Error(`${name} resolved path ${candidate} is outside workspacePath`);
    }
  }
  if (!isInside(guideIndexPath, guideWorkspacePath)) {
    throw new Error(`guideIndexPath ${guideIndexPath} is outside workspacePath`);
  }
  return {
    workspacePath,
    toolCatalogPath,
    guideIndexPath,
    guideWorkspacePath,
    guideRootPath,
    guideIndexSha256: descriptor.guideIndexSha256,
    activeTurnPath,
    analysisContextViewPath,
    trajectoryRequestsPath,
    trajectoryCaptureStatePath,
    trajectoryAllowedRefsPath,
    trajectoryAcksPath,
    piRuntime: descriptor.piRuntime,
  };
}

function validateContract(contract, descriptor) {
  if (!isPlainObject(contract)) {
    throw new TypeError("capability contract must be a plain object");
  }
  for (const name of ["name", "capability", "description"]) {
    if (
      typeof contract[name] !== "string" ||
      contract[name].length === 0 ||
      (name === "name" && !TOOL_NAME_PATTERN.test(contract[name]))
    ) {
      throw new TypeError(`capability contract ${name} must be a non-empty string`);
    }
  }
  if (
    !contract.name.startsWith(descriptor.toolNamePrefix) ||
    contract.name.length === descriptor.toolNamePrefix.length ||
    contract.name === `${descriptor.toolNamePrefix}query`
  ) {
    throw new TypeError("capability contract name must use the descriptor tool prefix");
  }
  if (!isPlainObject(contract.input_schema)) {
    throw new TypeError("capability contract input_schema must be an object");
  }
}

function selectedBindingRuntime(value) {
  if (SELECTED_BINDING_RUNTIMES.has(value)) {
    return value;
  }
  const runtime = validateRuntimeDescriptor(value);
  const domain = runtime.domains[0];
  const selected = Object.freeze({
    ...domain,
    toolNamePrefix: toolPrefixFromGuideName(domain.guideToolName),
    contextToolName: runtime.core.contextToolName,
    decisionToolName: runtime.core.decisionToolName,
    activeTurnPath: runtime.core.activeTurnPath,
    analysisContextViewPath: runtime.core.analysisContextViewPath,
    trajectoryRequestsPath: runtime.core.trajectoryRequestsPath,
    trajectoryCaptureStatePath: runtime.core.trajectoryCaptureStatePath,
    trajectoryAllowedRefsPath: runtime.core.trajectoryAllowedRefsPath,
    trajectoryAcksPath: runtime.core.trajectoryAcksPath,
    piRuntime: runtime.application.piRuntime,
  });
  SELECTED_BINDING_RUNTIMES.add(selected);
  if (LEGACY_RUNTIME_DESCRIPTORS.has(runtime)) {
    LEGACY_SELECTED_BINDING_RUNTIMES.add(selected);
  }
  return selected;
}

function requireExactKeys(value, allowed, label, { required = [] } = {}) {
  if (!isPlainObject(value)) {
    throw new TypeError(`${label} must be a plain object`);
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || !allowed.has(key)) {
      throw new TypeError(`${label} contains an unknown field: ${String(key)}`);
    }
  }
  for (const key of required) {
    if (!Object.hasOwn(value, key)) {
      throw new TypeError(`${label} is missing required field: ${key}`);
    }
  }
}

function requireNonEmptyString(value, name) {
  if (typeof value !== "string" || value.length === 0) {
    throw new TypeError(`runtime descriptor ${name} must be a non-empty string`);
  }
  return value;
}

function toolPrefixFromGuideName(value) {
  const suffix = "guide_open";
  if (typeof value !== "string" || !value.endsWith(suffix)) {
    throw new TypeError("runtime descriptor domain guideToolName must end with guide_open");
  }
  const prefix = value.slice(0, -suffix.length);
  return requirePattern(prefix, "domain toolNamePrefix", TOOL_PREFIX_PATTERN);
}

function requireInside(candidate, root, name) {
  if (!isInside(candidate, root)) {
    throw new TypeError(`runtime descriptor domain ${name} is outside workspacePath`);
  }
  return candidate;
}

function compactObject(value) {
  return Object.fromEntries(Object.entries(value).filter(([, entry]) => entry !== undefined));
}

function requirePattern(value, name, pattern) {
  if (typeof value !== "string" || !pattern.test(value)) {
    throw new TypeError(`runtime descriptor ${name} is invalid`);
  }
  return value;
}

function requireExecutable(value) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value === "." ||
    value === ".." ||
    !EXECUTABLE_PATTERN.test(value) ||
    basename(value) !== value
  ) {
    throw new TypeError("runtime descriptor executable must be a basename");
  }
  return value;
}

function requireStringArray(value, name) {
  if (!Array.isArray(value) || !value.every((entry) => typeof entry === "string")) {
    throw new TypeError(`runtime descriptor ${name} must contain only strings`);
  }
  return value;
}

function requireBoundedToolName(value, name, prefix) {
  if (
    typeof value !== "string" ||
    !TOOL_NAME_PATTERN.test(value) ||
    value.length === prefix.length ||
    !value.startsWith(prefix)
  ) {
    throw new TypeError(`runtime descriptor ${name} must use the tool prefix`);
  }
  return value;
}

function requireAbsolutePath(value, name) {
  if (typeof value !== "string" || value.length === 0 || !isAbsolute(value)) {
    throw new TypeError(`runtime descriptor ${name} must be an absolute path`);
  }
  return resolve(value);
}

function cloneRuntime(value) {
  if (!isPlainObject(value)) {
    throw new TypeError("runtime descriptor piRuntime must be a plain object");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || !RUNTIME_IDENTITY_KEY_SET.has(key)) {
      throw new TypeError(`runtime descriptor piRuntime contains an unknown field: ${String(key)}`);
    }
  }
  if (Reflect.ownKeys(value).length !== RUNTIME_IDENTITY_KEYS.length) {
    throw new TypeError("runtime descriptor piRuntime keys must be exactly the runtime identity keys");
  }
  const runtime = {};
  for (const key of RUNTIME_IDENTITY_KEYS) {
    const entry = value[key];
    if (typeof entry !== "string" || entry.length === 0) {
      throw new TypeError(`runtime descriptor piRuntime ${key} must be a non-empty string`);
    }
    runtime[key] = entry;
  }
  return Object.freeze(runtime);
}

function requiredExistingRealPath(value, name) {
  if (value === undefined) {
    throw new Error(`${name} path is required`);
  }
  try {
    return realpathSync(value);
  } catch (error) {
    throw new Error(`${name} path must resolve to an existing path: ${error.message}`);
  }
}

function requiredWritableRealPath(value, name) {
  if (value === undefined) {
    throw new Error(`${name} path is required`);
  }
  try {
    return realpathSync(value);
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw new Error(`${name} path must resolve to a writable path: ${error.message}`);
    }
    const parent = dirname(value);
    try {
      return resolve(realpathSync(parent), basename(value));
    } catch (parentError) {
      throw new Error(`${name} parent must resolve to an existing path: ${parentError.message}`);
    }
  }
}

function optionalExistingRealPath(value, name) {
  if (value === undefined || value === "") {
    return undefined;
  }
  return requiredExistingRealPath(value, name);
}

function optionalWritableRealPath(value, name) {
  if (value === undefined || value === "") {
    return undefined;
  }
  return requiredWritableRealPath(value, name);
}

function isInside(candidate, root) {
  const relationship = relative(root, candidate);
  return relationship === "" || (!relationship.startsWith("..") && !isAbsolute(relationship));
}

function selectedSecretNames(env) {
  return (env.CAPABILITY_AGENT_SECRET_ENV_NAMES ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
}

function isCredentialName(name) {
  return /(API_KEY|TOKEN|SECRET|AUTHORIZATION|CREDENTIAL|PASSWORD|PRIVATE_KEY|SECRET_ENV_NAMES)$/i.test(name);
}

function isCorrelatedResponse(response, requestId, descriptor) {
  return (
    response &&
    response.protocol === descriptor.protocol &&
    response.protocol_version === descriptor.protocolVersion &&
    response.request_id === requestId
  );
}

function transportError(
  requestId,
  descriptor,
  message,
  code = "capability_transport_error",
) {
  return {
    protocol: descriptor.protocol,
    protocol_version: descriptor.protocolVersion,
    request_id: requestId,
    ok: false,
    error: {
      code,
      phase: "execute",
      message,
    },
  };
}

function canonicalToolResult(capability, response) {
  if (response.ok === true) {
    const result = response.result ?? {};
    return {
      event: "tool_result",
      capability,
      ok: true,
      result,
      evidence_refs: evidenceRefs(result),
    };
  }
  const error = response.error ?? {};
  return {
    event: "tool_result",
    capability,
    ok: false,
    result: {},
    error,
    evidence_refs: evidenceRefs(error),
  };
}

function evidenceRefs(value) {
  const refs = [];
  if (typeof value?.evidence_ref === "string") {
    refs.push(value.evidence_ref);
  }
  if (Array.isArray(value?.evidence_refs)) {
    refs.push(...value.evidence_refs.filter((reference) => typeof reference === "string"));
  }
  return [...new Set(refs)];
}

function toolError(error, capability) {
  const details = {
    event: "tool_result",
    capability,
    ok: false,
    result: {},
    error,
    evidence_refs: [],
  };
  return {
    content: [{ type: "text", text: JSON.stringify(details) }],
    details,
    isError: true,
  };
}

function readJsonSync(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function readAllowedRefs(path) {
  const document = await readJson(path);
  if (
    !document ||
    !Array.isArray(document.refs) ||
    !document.refs.every((reference) => typeof reference === "string" && reference.length > 0)
  ) {
    throw new Error("trajectory allowed refs document is invalid");
  }
  return new Set(document.refs);
}

async function readActiveTurn(path) {
  const activeTurn = await readJson(path);
  if (typeof activeTurn?.turn_id !== "string" || typeof activeTurn?.turn_nonce !== "string") {
    throw new Error("active turn must contain turn_id and turn_nonce");
  }
  return {
    turn_id: activeTurn.turn_id,
    turn_nonce: activeTurn.turn_nonce,
  };
}

function decisionValidationError(params) {
  for (const name of ["intent", "decision", "next_action"]) {
    if (
      typeof params?.[name] !== "string" ||
      params[name].length < 1 ||
      params[name].length > 500
    ) {
      return `${name} must contain 1 to 500 characters`;
    }
  }
  if (
    !Array.isArray(params?.refs) ||
    params.refs.length > 20 ||
    !params.refs.every((reference) => typeof reference === "string" && reference.length > 0)
  ) {
    return "refs must contain at most 20 non-empty strings";
  }
  return undefined;
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}
