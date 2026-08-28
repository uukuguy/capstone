import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "@earendil-works/pi-ai";
import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { basename, dirname, isAbsolute, relative, resolve } from "node:path";
import { readFileSync, realpathSync } from "node:fs";
import { readFile, realpath } from "node:fs/promises";

import { configureModelRequestCapture } from "./model-request-capture.mjs";

const DESCRIPTOR_KEYS = new Set([
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
  "workspacePath",
  "activeTurnPath",
  "analysisContextViewPath",
  "trajectoryRequestsPath",
  "trajectoryCaptureStatePath",
  "trajectoryAllowedRefsPath",
  "trajectoryAcksPath",
  "piRuntime",
]);
const PROTOCOL_PATTERN = /^[a-z][a-z0-9.-]*$/;
const PROTOCOL_VERSION_PATTERN = /^\d+\.\d+$/;
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
const DEFAULT_TRANSPORT_LIMITS = Object.freeze({
  timeoutMs: 60_000,
  maxOutputBytes: 1_048_576,
});
const MAX_TRANSPORT_LIMITS = Object.freeze({
  timeoutMs: 120_000,
  maxOutputBytes: 4_194_304,
});

/**
 * Validate and detach the controller-owned runtime descriptor.
 *
 * Pi receives only the returned immutable copy. In particular, the process
 * executable and argument template can never be supplied by tool input.
 */
export function validateRuntimeDescriptor(value) {
  if (!isPlainObject(value)) {
    throw new TypeError("runtime descriptor must be a plain object");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || !DESCRIPTOR_KEYS.has(key)) {
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
  ]) {
    if (value[key] !== undefined) {
      descriptor[key] = requireAbsolutePath(value[key], key);
    }
  }
  if (value.piRuntime !== undefined) {
    descriptor.piRuntime = cloneRuntime(value.piRuntime);
  }

  descriptor.executableArgs = Object.freeze([...descriptor.executableArgs]);
  return Object.freeze(descriptor);
}

export function buildCapabilityRequest(descriptor, capability, params, requestId = randomUUID()) {
  const runtime = validateRuntimeDescriptor(descriptor);
  if (typeof capability !== "string" || capability.length === 0) {
    throw new TypeError("capability must be a non-empty string");
  }
  if (typeof requestId !== "string" || requestId.length === 0) {
    throw new TypeError("requestId must be a non-empty string");
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
  const runtime = validateRuntimeDescriptor(descriptor);
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
  const runtime = validateRuntimeDescriptor(descriptor);
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
    const catalog = readJsonSync(paths.toolCatalogPath);
    if (!Array.isArray(catalog.tools)) {
      throw new Error("tool catalog must contain a tools array");
    }
    for (const contract of catalog.tools) {
      if (contract.name === runtime.decisionToolName) {
        continue;
      }
      pi.registerTool(
        buildTool(runtime, contract, (payload) => runCapability(payload, runtime, selectedNames)),
      );
    }
    pi.registerTool(createGuideTool(runtime, paths.guideIndexPath));
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
  const runtime = validateRuntimeDescriptor(descriptor);
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

function createGuideTool(descriptor, guideIndexPath) {
  const guideIndex = readJsonSync(guideIndexPath);
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
      const currentIndex = await readJson(guideIndexPath);
      const root = await realpath(String(currentIndex.root));
      const resourcePath = currentIndex.resources?.[params.resource_id];
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
      let resolvedPath;
      try {
        resolvedPath = await realpath(resourcePath);
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
      if (!isInside(resolvedPath, root)) {
        return toolError(
          {
            code: "guide_path_rejected",
            phase: "resolve",
            message: "guide resource path is outside the published guide root",
          },
          descriptor.guideToolName,
        );
      }
      const text = await readFile(resolvedPath, "utf8");
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
    },
  });
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
  const workspacePath = requiredExistingRealPath(descriptor.workspacePath, "workspacePath");
  const toolCatalogPath = requiredExistingRealPath(descriptor.toolCatalogPath, "toolCatalogPath");
  const guideIndexPath = requiredExistingRealPath(descriptor.guideIndexPath, "guideIndexPath");
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
  for (const [name, candidate] of [
    ["toolCatalogPath", toolCatalogPath],
    ["guideIndexPath", guideIndexPath],
    ["activeTurnPath", activeTurnPath],
    ["analysisContextViewPath", analysisContextViewPath],
    ["trajectoryRequestsPath", trajectoryRequestsPath],
    ["trajectoryCaptureStatePath", trajectoryCaptureStatePath],
    ["trajectoryAllowedRefsPath", trajectoryAllowedRefsPath],
  ]) {
    if (candidate !== undefined && !isInside(candidate, workspacePath)) {
      throw new Error(`${name} resolved path ${candidate} is outside workspacePath`);
    }
  }
  return {
    workspacePath,
    toolCatalogPath,
    guideIndexPath,
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
