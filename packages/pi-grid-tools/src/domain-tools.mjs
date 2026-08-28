import {
  buildCapabilityRequest,
  createCapabilityTool,
  createDomainToolsExtension,
  runCapability,
  sanitizeEnvironment as sanitizeCapabilityEnvironment,
} from "@capability-agent/pi-tools";
import { basename, dirname, isAbsolute, relative, resolve } from "node:path";
import { readFileSync, realpathSync } from "node:fs";

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
const LEGACY_FORBIDDEN_TOOL_NAMES = new Set(["bash", "shell", "read", "write", "edit"]);

export function sanitizeEnvironment(env, selectedNames = []) {
  return sanitizeCapabilityEnvironment(env, ["GRID_AGENT_SECRET_ENV_NAMES", ...selectedNames]);
}

export function buildGridRequest(capability, params, requestId) {
  return buildCapabilityRequest(GRID_DESCRIPTOR, capability, params, requestId);
}

export function createGridTool(contract, runner) {
  if (runner !== undefined) {
    return createCompatibleGridTool(GRID_DESCRIPTOR, contract, runner);
  }
  return createCompatibleGridTool(GRID_DESCRIPTOR, contract, (payload) => {
    const workspacePath = requiredExistingRealPath(process.env, "GRID_AGENT_WORKSPACE");
    return runCapability(
      payload,
      Object.freeze({
        ...GRID_DESCRIPTOR,
        executableArgs: Object.freeze(["request", "--workspace", workspacePath]),
      }),
      ["GRID_AGENT_SECRET_ENV_NAMES"],
    );
  });
}

export default function domainToolsExtension(pi) {
  const paths = runtimePaths(process.env);
  return createDomainToolsExtension(gridDescriptor(paths), {
    createTool: createCompatibleGridTool,
  })(pi);
}

function createCompatibleGridTool(descriptor, contract, runner) {
  const originalName = contract.name;
  if (originalName.startsWith(descriptor.toolNamePrefix)) {
    return createCapabilityTool(descriptor, contract, runner);
  }
  if (LEGACY_FORBIDDEN_TOOL_NAMES.has(originalName)) {
    throw new TypeError("capability contract name must use the descriptor tool prefix");
  }
  const tool = createCapabilityTool(
    descriptor,
    { ...contract, name: `${descriptor.toolNamePrefix}${originalName}` },
    runner,
  );
  tool.name = originalName;
  tool.label = originalName;
  return tool;
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

function runtimePaths(env) {
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
