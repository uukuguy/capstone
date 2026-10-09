import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { createInterface } from "node:readline";

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}

export function verifyMcpPublication(session, config) {
  if (!config.mcp) return {};
  for (const [name, schema] of Object.entries(config.mcp.descriptor.tool_schemas)) {
    const actual = session.getAllTools().find(tool => tool.name === name);
    const owners = session.resourceLoader.getExtensions().extensions.filter(extension => extension.tools.has(name));
    if (!actual || actual.description !== schema.description ||
        JSON.stringify(canonical(actual.parameters)) !== JSON.stringify(canonical(schema.inputSchema)) ||
        owners.length !== 1 || owners[0].resolvedPath !== config.extensions.at(-1)) {
      throw new Error("Native MCP tool schema or extension owner changed");
    }
  }
  return config.mcp.descriptor.tool_schema_hashes;
}

// Only a host-validated typed invocation can enable native command expansion.
export async function promptInput(session, input, skillName) {
  if (input.kind === "text") {
    return session.prompt(input.text, { expandPromptTemplates: false });
  }
  const skills = session.resourceLoader.getSkills().skills.filter(s => s.name === skillName);
  const prompts = session.resourceLoader.getPrompts?.().prompts ?? session.resourceLoader.getPromptTemplates?.() ?? [];
  if (input.kind !== "skill_invocation" || !/^[a-z0-9][a-z0-9-]*$/.test(skillName ?? "") ||
      skills.length !== 1 || session.extensionRunner.getCommand(`skill:${skillName}`) ||
      prompts.some(p => p.name === `skill:${skillName}`)) {
    throw new Error("Native skill command is unavailable or has a collision");
  }
  return session.prompt(`/skill:${skillName} ${input.text}`, { expandPromptTemplates: true });
}

async function main() {
  const config = JSON.parse(readFileSync(process.argv[2], "utf8"));
  const sdk = await import(pathToFileURL(config.sdk).href);
  const settingsManager = sdk.SettingsManager.inMemory({ ...config.settings, retry: { enabled: false } });
  const loader = new sdk.DefaultResourceLoader({ cwd: process.cwd(), agentDir: process.env.PI_CODING_AGENT_DIR,
    settingsManager, additionalExtensionPaths: config.extensions, noThemes: true,
    noContextFiles: true, agentsFilesOverride: () => ({ agentsFiles: config.contextFiles }),
    systemPromptOverride: () => config.systemPrompt ?? undefined,
    appendSystemPromptOverride: () => config.appendSystemPrompt ?? [],
    skillsOverride: current => ({ ...current, skills: current.skills.filter(s => config.allowedSkills.includes(s.name)) }) });
  await loader.reload();
  const errors = [...loader.getExtensions().errors, ...loader.getSkills().diagnostics.filter(d => d.type === "collision")];
  if (errors.length) throw new Error("Native resources failed to load");
  const modelRuntime = await sdk.ModelRuntime.create({ authPath: `${process.env.PI_CODING_AGENT_DIR}/auth.json`,
    modelsPath: `${process.env.PI_CODING_AGENT_DIR}/models.json`, allowModelNetwork: false });
  const model = modelRuntime.getModel("capstone-general", config.model);
  if (!model) throw new Error("Managed native model is unavailable");
  const { session } = await sdk.createAgentSession({ cwd: process.cwd(), agentDir: process.env.PI_CODING_AGENT_DIR,
    modelRuntime, model, resourceLoader: loader, settingsManager,
    sessionManager: sdk.SessionManager.inMemory() });
  try {
    session.subscribe(event => process.stdout.write(JSON.stringify(event) + "\n"));
    await session.bindExtensions({ onError: () => { throw new Error("Native extension failed"); } });
    const skills = loader.getSkills().skills.map(s => ({ name: s.name,
      sha256: createHash("sha256").update(readFileSync(s.filePath)).digest("hex") }));
    const toolHashes = verifyMcpPublication(session, config);
    process.stdout.write(JSON.stringify({ type: "general_pi_inventory", tools: session.getActiveToolNames(), skills,
      tool_schema_hashes: toolHashes, adapter_sha256: config.adapter_sha256 }) + "\n");
    if (config.inventoryOnly) return;
    const lines = createInterface({ input: process.stdin });
    for await (const line of lines) {
      if (Buffer.byteLength(line) > 262144) throw new Error("Native input exceeds bounds");
      const frame = JSON.parse(line);
      if (frame.type !== "prompt") throw new Error("Invalid native request");
      await promptInput(session, config.input, config.skillName);
      break;
    }
    lines.close();
  } finally { session.dispose(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(() => { process.stdout.write(JSON.stringify({ type: "response", success: false }) + "\n"); process.exitCode = 1; });
}
