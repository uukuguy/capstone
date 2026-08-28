import {
  buildCapabilityRequest,
  createCapabilityTool,
  createDomainToolsExtension,
  runCapability,
  sanitizeEnvironment as sanitizeCapabilityEnvironment,
  validateRuntimeDescriptor,
} from "@capability-agent/pi-tools";
import { basename, dirname, isAbsolute, relative, resolve } from "node:path";
import { readFileSync, realpathSync } from "node:fs";

const RUNTIME_DESCRIPTOR_ENV = "CAPABILITY_AGENT_RUNTIME_DESCRIPTOR";
const SNAKE_DESCRIPTOR_KEYS = new Set([
  "protocol",
  "protocol_version",
  "executable",
  "executable_args",
  "tool_name_prefix",
  "guide_tool_name",
  "context_tool_name",
  "decision_tool_name",
  "tool_catalog_path",
  "guide_index_path",
  "workspace_path",
  "active_turn_path",
  "analysis_context_view_path",
  "trajectory_requests_path",
  "trajectory_capture_state_path",
  "trajectory_allowed_refs_path",
  "trajectory_acks_path",
  "pi_runtime",
]);
const GRID_DESCRIPTOR = Object.freeze({
  protocol: "grid-capability",
  protocolVersion: "1.0",
  executable: "gridctl",
  executableArgs: Object.freeze([]),
  toolNamePrefix: "grid_",
  guideToolName: "grid_guide_open",
  contextToolName: "grid_analysis_context_get",
  decisionToolName: "grid_record_decision",
});

export function sanitizeEnvironment(env, selectedNames = []) {
  return sanitizeCapabilityEnvironment(env, [
    "GRID_AGENT_SECRET_ENV_NAMES",
    ...selectedGridSecretNames(env),
    ...selectedNames,
  ]);
}

export function buildGridRequest(capability, params, requestId) {
  return buildCapabilityRequest(GRID_DESCRIPTOR, capability, params, requestId);
}

export function createGridTool(contract, runner) {
  if (runner !== undefined) {
    return createCapabilityTool(GRID_DESCRIPTOR, contract, runner);
  }
  const descriptor = runtimeDescriptor(process.env);
  return createCapabilityTool(descriptor, contract, (payload) => {
    return runCapability(
      payload,
      descriptor,
      selectedGridSecretNames(process.env),
    );
  });
}

export default function domainToolsExtension(pi) {
  return createDomainToolsExtension(runtimeDescriptor(process.env), {
    selectedSecretNames: selectedGridSecretNames(process.env),
  })(pi);
}

function selectedGridSecretNames(env) {
  return (env.GRID_AGENT_SECRET_ENV_NAMES ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
}

function runtimeDescriptor(env) {
  if (env[RUNTIME_DESCRIPTOR_ENV] !== undefined && env[RUNTIME_DESCRIPTOR_ENV] !== "") {
    return descriptorFromRuntimeFile(env);
  }
  return gridDescriptor(legacyRuntimePaths(env));
}

function descriptorFromRuntimeFile(env) {
  const descriptorPath = requiredExistingRealPath(env, RUNTIME_DESCRIPTOR_ENV);
  const raw = readRuntimeDescriptor(descriptorPath);
  const descriptor = snakeToRuntimeDescriptor(raw, env);
  assertGridRuntimeDescriptor(descriptor);
  return validateRuntimeDescriptor(descriptor);
}

function readRuntimeDescriptor(path) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`${RUNTIME_DESCRIPTOR_ENV} must contain valid JSON: ${error.message}`);
  }
  if (!isPlainObject(raw)) {
    throw new Error(`${RUNTIME_DESCRIPTOR_ENV} must contain a JSON object`);
  }
  for (const key of Object.keys(raw)) {
    if (!SNAKE_DESCRIPTOR_KEYS.has(key)) {
      throw new Error(`${RUNTIME_DESCRIPTOR_ENV} contains unknown field ${key}`);
    }
  }
  return raw;
}

function snakeToRuntimeDescriptor(raw, _env) {
  const descriptor = {
    protocol: requiredSnakeString(raw, "protocol"),
    protocolVersion: requiredSnakeString(raw, "protocol_version"),
    executable: requiredSnakeString(raw, "executable"),
    executableArgs: requiredSnakeStringArray(raw, "executable_args"),
    toolNamePrefix: requiredSnakeString(raw, "tool_name_prefix"),
    guideToolName: requiredSnakeString(raw, "guide_tool_name"),
    contextToolName: requiredSnakeString(raw, "context_tool_name"),
    decisionToolName: requiredSnakeString(raw, "decision_tool_name"),
    workspacePath: requiredSnakeString(raw, "workspace_path"),
    toolCatalogPath: requiredSnakeString(raw, "tool_catalog_path"),
    guideIndexPath: requiredSnakeString(raw, "guide_index_path"),
    activeTurnPath: optionalSnakeString(raw, "active_turn_path"),
    analysisContextViewPath: optionalSnakeString(raw, "analysis_context_view_path"),
    trajectoryRequestsPath: optionalSnakeString(raw, "trajectory_requests_path"),
    trajectoryCaptureStatePath: optionalSnakeString(raw, "trajectory_capture_state_path"),
    trajectoryAllowedRefsPath: optionalSnakeString(raw, "trajectory_allowed_refs_path"),
    trajectoryAcksPath: optionalSnakeString(raw, "trajectory_acks_path"),
    piRuntime: raw.pi_runtime ?? undefined,
  };
  return Object.fromEntries(Object.entries(descriptor).filter(([, value]) => value !== undefined));
}

function assertGridRuntimeDescriptor(descriptor) {
  for (const [field, expected] of [
    ["protocol", GRID_DESCRIPTOR.protocol],
    ["protocolVersion", GRID_DESCRIPTOR.protocolVersion],
    ["executable", GRID_DESCRIPTOR.executable],
    ["toolNamePrefix", GRID_DESCRIPTOR.toolNamePrefix],
    ["guideToolName", GRID_DESCRIPTOR.guideToolName],
    ["contextToolName", GRID_DESCRIPTOR.contextToolName],
    ["decisionToolName", GRID_DESCRIPTOR.decisionToolName],
  ]) {
    if (descriptor[field] !== expected) {
      throw new Error(`${RUNTIME_DESCRIPTOR_ENV} ${field} must be ${expected}`);
    }
  }
  const expectedArgs = ["request", "--workspace", descriptor.workspacePath];
  if (
    descriptor.executableArgs.length !== expectedArgs.length ||
    descriptor.executableArgs.some((entry, index) => entry !== expectedArgs[index])
  ) {
    throw new Error(`${RUNTIME_DESCRIPTOR_ENV} executableArgs must be request,--workspace,<workspacePath>`);
  }
}

function gridDescriptor(paths) {
  return Object.freeze({
    ...GRID_DESCRIPTOR,
    executableArgs: Object.freeze(["request", "--workspace", paths.workspacePath]),
    toolCatalogPath: paths.toolCatalogPath,
    guideIndexPath: paths.guideIndexPath,
    workspacePath: paths.workspacePath,
    activeTurnPath: paths.activeTurnPath,
    analysisContextViewPath: paths.analysisContextViewPath,
    trajectoryRequestsPath: paths.trajectoryRequestsPath,
    trajectoryCaptureStatePath: paths.trajectoryCaptureStatePath,
    trajectoryAllowedRefsPath: paths.trajectoryAllowedRefsPath,
    trajectoryAcksPath: paths.trajectoryAcksPath,
    piRuntime: paths.piRuntime,
  });
}

function legacyRuntimePaths(env) {
  const workspacePath = requiredExistingRealPath(env, "GRID_AGENT_WORKSPACE");
  const toolCatalogPath = requiredExistingRealPath(env, "GRID_AGENT_TOOL_CATALOG");
  const guideIndexPath = requiredExistingRealPath(env, "GRID_AGENT_GUIDE_INDEX");
  const activeTurnPath = optionalWritableRealPath(env, "GRID_AGENT_ACTIVE_TURN");
  const analysisContextViewPath = optionalExistingRealPath(env, "GRID_AGENT_ANALYSIS_CONTEXT_VIEW");
  const trajectoryRequestsPath = optionalExistingRealPath(env, "GRID_AGENT_TRAJECTORY_REQUESTS");
  const trajectoryCaptureStatePath = optionalExistingRealPath(
    env,
    "GRID_AGENT_TRAJECTORY_CAPTURE_STATE",
  );
  const trajectoryAllowedRefsPath = optionalExistingRealPath(
    env,
    "GRID_AGENT_TRAJECTORY_ALLOWED_REFS",
  );
  const trajectoryAcksPath = optionalExistingRealPath(env, "GRID_AGENT_TRAJECTORY_ACKS");
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
    throw new Error("trajectory capture requires GRID_AGENT_ACTIVE_TURN");
  }
  for (const [name, candidate] of [
    ["GRID_AGENT_TOOL_CATALOG", toolCatalogPath],
    ["GRID_AGENT_GUIDE_INDEX", guideIndexPath],
    ["GRID_AGENT_ACTIVE_TURN", activeTurnPath],
    ["GRID_AGENT_ANALYSIS_CONTEXT_VIEW", analysisContextViewPath],
    ["GRID_AGENT_TRAJECTORY_REQUESTS", trajectoryRequestsPath],
    ["GRID_AGENT_TRAJECTORY_CAPTURE_STATE", trajectoryCaptureStatePath],
    ["GRID_AGENT_TRAJECTORY_ALLOWED_REFS", trajectoryAllowedRefsPath],
  ]) {
    if (candidate !== undefined && !isInside(candidate, workspacePath)) {
      throw new Error(`${name} resolved path ${candidate} is outside GRID_AGENT_WORKSPACE`);
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
    piRuntime: runtimeIdentity(env),
  };
}

function runtimeIdentity(env) {
  if (
    env.GRID_AGENT_PI_CODING_AGENT_VERSION === undefined &&
    env.GRID_AGENT_PI_AI_VERSION === undefined &&
    env.GRID_AGENT_PI_SOURCE_COMMIT === undefined &&
    env.GRID_AGENT_PI_PATCH_SET_SHA256 === undefined
  ) {
    return undefined;
  }
  return {
    pi_coding_agent_version: requiredString(env, "GRID_AGENT_PI_CODING_AGENT_VERSION"),
    pi_ai_version: requiredString(env, "GRID_AGENT_PI_AI_VERSION"),
    pi_source_commit: requiredString(env, "GRID_AGENT_PI_SOURCE_COMMIT"),
    pi_patch_set_sha256: requiredString(env, "GRID_AGENT_PI_PATCH_SET_SHA256"),
  };
}

function requiredString(env, name) {
  const value = env[name];
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${name} must be a non-empty string`);
  }
  return value;
}

function requiredAbsolutePath(env, name) {
  const value = env[name];
  if (typeof value !== "string" || value.length === 0 || !isAbsolute(value)) {
    throw new Error(`${name} must be an absolute path`);
  }
  return resolve(value);
}

function requiredExistingRealPath(env, name) {
  const path = requiredAbsolutePath(env, name);
  try {
    return realpathSync(path);
  } catch (error) {
    throw new Error(`${name} must resolve to an existing path: ${error.message}`);
  }
}

function requiredWritableRealPath(env, name) {
  const path = requiredAbsolutePath(env, name);
  try {
    return realpathSync(path);
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw new Error(`${name} must resolve to a writable path: ${error.message}`);
    }
    const parent = dirname(path);
    try {
      return resolve(realpathSync(parent), basename(path));
    } catch (parentError) {
      throw new Error(`${name} parent must resolve to an existing path: ${parentError.message}`);
    }
  }
}

function optionalExistingRealPath(env, name) {
  if (env[name] === undefined || env[name] === "") {
    return undefined;
  }
  return requiredExistingRealPath(env, name);
}

function optionalWritableRealPath(env, name) {
  if (env[name] === undefined || env[name] === "") {
    return undefined;
  }
  return requiredWritableRealPath(env, name);
}

function isInside(candidate, root) {
  const relationship = relative(root, candidate);
  return relationship === "" || (!relationship.startsWith("..") && !isAbsolute(relationship));
}

function requiredSnakeString(value, name) {
  const entry = value[name];
  if (typeof entry !== "string" || entry.length === 0) {
    throw new Error(`${RUNTIME_DESCRIPTOR_ENV} ${name} must be a non-empty string`);
  }
  return entry;
}

function optionalSnakeString(value, name) {
  const entry = value[name];
  if (entry === undefined || entry === null || entry === "") {
    return undefined;
  }
  if (typeof entry !== "string") {
    throw new Error(`${RUNTIME_DESCRIPTOR_ENV} ${name} must be a string`);
  }
  return entry;
}

function requiredSnakeStringArray(value, name) {
  const entry = value[name];
  if (!Array.isArray(entry) || !entry.every((item) => typeof item === "string")) {
    throw new Error(`${RUNTIME_DESCRIPTOR_ENV} ${name} must contain only strings`);
  }
  return entry;
}

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null)
  );
}
