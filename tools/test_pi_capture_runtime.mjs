#!/usr/bin/env node

import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { isDeepStrictEqual } from "node:util";

const root = resolve(import.meta.dirname, "..");
const requestedSource = argumentValue("--runtime-source");
const mode = argumentValue("--mode") ?? "success";
const wrapper = argumentValue("--wrapper") ?? "grid";
if (!new Set(["success", "failure"]).has(mode))
	throw new Error("--mode must be success or failure");
if (!new Set(["generic", "grid"]).has(wrapper))
	throw new Error("--wrapper must be generic or grid");
const source = requestedSource ? resolve(requestedSource) : managedSource();
let assertionCount = 0;
const lock = JSON.parse(
	readFileSync(join(root, "configs/runtime/pi-runtime.lock.json"), "utf8"),
);
const patches = lock.patches.map(({ path, sha256 }) => {
	check(
		hash(readFileSync(join(root, "configs/runtime", path))) === sha256,
		"runtime patch bytes differ from lock",
	);
	return { path, sha256 };
});
const patchSet = hash(JSON.stringify(patches));
const runtimeIdentity = {
	pi_coding_agent_version: lock.package.version,
	pi_ai_version: lock.runtime.pi_ai_version,
	pi_source_commit: lock.source.commit,
	pi_patch_set_sha256: patchSet,
};
check(
	execFileSync("git", ["rev-parse", "HEAD"], {
		cwd: source,
		encoding: "utf8",
	}).trim() === lock.source.commit,
	"runtime checkout differs from lock",
);
check(
	JSON.parse(
		readFileSync(join(source, "packages/coding-agent/package.json"), "utf8"),
	).version === lock.package.version,
	"runtime package differs from lock",
);
const sdkPath = join(source, "packages/coding-agent/dist/core/sdk.js");
if (!existsSync(sdkPath))
	throw new Error(`built Pi SDK is unavailable: ${sdkPath}`);
process.env.PI_OFFLINE = "1";

const sdk = await import(pathToFileURL(sdkPath));
const ai = await import(
	pathToFileURL(join(source, "packages/ai/dist/index.js"))
);
const settings = await import(
	pathToFileURL(
		join(source, "packages/coding-agent/dist/core/settings-manager.js"),
	)
);
const sessions = await import(
	pathToFileURL(
		join(source, "packages/coding-agent/dist/core/session-manager.js"),
	)
);
const runtimeModule = await import(
	pathToFileURL(
		join(source, "packages/coding-agent/dist/core/model-runtime.js"),
	)
);

const sandbox = await mkdtemp(join(tmpdir(), "pi-capture-runtime-"));
let calls = 0;
try {
	const paths = await fixturePaths(sandbox);
	await writeExtension(paths.extensions, mode, wrapper, paths);
	const model = {
		id: "smoke",
		name: "smoke",
		api: "openai-completions",
		provider: "smoke",
		baseUrl: "https://invalid",
		reasoning: false,
		input: ["text"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow: 1024,
		maxTokens: 64,
	};
	const modelRuntime = await runtimeModule.ModelRuntime.create({
		authPath: join(paths.agent, "auth.json"),
		modelsPath: null,
		refreshOnCreate: false,
	});
	modelRuntime.streamSimple = async (_model, context) => {
		calls += 1;
		const request = JSON.parse(
			await readFile(
				join(paths.requests, "turn-smoke-r001", "input.json"),
				"utf8",
			),
		);
		check(
			request.turn_id === "turn-smoke",
			"provider entered before durable capture",
		);
		check(
			!existsSync(join(paths.acks, "turn-smoke-r001.json")),
			"capture waited for an observer acknowledgement",
		);
		check(
			request.semantic_request.context.messages[0].content[0].text ===
				context.messages[0].content,
			"captured semantic message differs from runtime input",
		);
		check(
			isDeepStrictEqual(request.runtime, runtimeIdentity),
			"captured runtime identity differs from tested runtime",
		);
		check(
			request.schema_version ===
				(wrapper === "grid"
					? "grid-model-request-input/2.0"
					: "capability-model-request-input/1.0"),
			"wrong wrapper schema",
		);
		const stream = ai.createAssistantMessageEventStream();
		stream.end({
			role: "assistant",
			content: [{ type: "text", text: "ok" }],
			api: "openai-completions",
			provider: "smoke",
			model: "smoke",
			usage: {
				input: 0,
				output: 0,
				cacheRead: 0,
				cacheWrite: 0,
				totalTokens: 0,
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
			},
			stopReason: "stop",
			timestamp: Date.now(),
		});
		return stream;
	};
	const { session } = await sdk.createAgentSession({
		cwd: paths.cwd,
		agentDir: paths.agent,
		model,
		modelRuntime,
		settingsManager: settings.SettingsManager.inMemory({}),
		sessionManager: sessions.SessionManager.inMemory(paths.cwd),
	});
	let failed = false;
	let stopReason;
	try {
		const stream = await session.agent.streamFunction(model, {
			messages: [{ role: "user", content: "smoke", timestamp: Date.now() }],
			tools: [],
		});
		stopReason = (await stream.result()).stopReason;
	} catch (error) {
		if (mode !== "failure" || !String(error).includes("capture rejected"))
			throw error;
		failed = true;
	}
	session.dispose();
	const input = existsSync(
		join(paths.requests, "turn-smoke-r001", "input.json"),
	);
	if (mode === "success")
		check(
			input && calls === 1 && !failed && stopReason === "stop",
			"success capture smoke failed",
		);
	if (mode === "failure") {
		check(calls === 0 && failed, "capture failure did not stop provider");
		check(
			(await readFile(
				join(paths.requests, "turn-smoke-r001", "input.json"),
				"utf8",
			)) === "sentinel",
			"capture replaced existing input",
		);
	}
	process.stdout.write(
		`${JSON.stringify({ wrapper, mode, provider_calls: calls, durable_input: input, acknowledgement_present: existsSync(join(paths.acks, "turn-smoke-r001.json")), runtime_commit: lock.source.commit, patch_set_sha256: patchSet, assertion_count: assertionCount, success: true })}\n`,
	);
} finally {
	await rm(sandbox, { recursive: true, force: true });
}

function managedSource() {
	const active = join(root, ".grid-agent/runtime/pi/active");
	if (!existsSync(active))
		throw new Error("managed Pi runtime active marker is unavailable");
	return readFileSync(active, "utf8").split("\n", 1)[0];
}
function argumentValue(flag) {
	const i = process.argv.indexOf(flag);
	return i < 0 ? undefined : process.argv[i + 1];
}
function hash(value) {
	return createHash("sha256").update(value).digest("hex");
}
function check(condition, message) {
	assertionCount += 1;
	if (!condition) throw new Error(message);
}
async function fixturePaths(base) {
	const p = {
		cwd: join(base, "cwd"),
		agent: join(base, "agent"),
		extensions: join(base, "agent/extensions"),
		requests: join(base, "requests"),
		acks: join(base, "acks"),
		active: join(base, "active.json"),
		state: join(base, "state.json"),
		allowed: join(base, "allowed.json"),
	};
	await Promise.all([
		mkdir(p.cwd, { recursive: true }),
		mkdir(p.extensions, { recursive: true }),
		mkdir(p.requests),
		mkdir(p.acks),
	]);
	await Promise.all([
		writeFile(p.active, JSON.stringify({ turn_id: "turn-smoke" })),
		writeFile(
			p.state,
			JSON.stringify({
				source_event_sequences: [1],
				context_revision: 1,
				context_state_hash: "0".repeat(64),
			}),
		),
		writeFile(p.allowed, "[]"),
	]);
	return p;
}
async function writeExtension(dir, mode, wrapper, p) {
	const module = pathToFileURL(
		join(
			root,
			`packages/pi-${wrapper === "grid" ? "grid" : "capability"}-tools/src/model-request-capture.mjs`,
		),
	).href;
	if (mode === "failure")
		await mkdir(join(p.requests, "turn-smoke-r001"), { recursive: true }),
			await writeFile(
				join(p.requests, "turn-smoke-r001", "input.json"),
				"sentinel",
			);
	const source = `import { configureModelRequestCapture } from ${JSON.stringify(module)}; export default (pi) => configureModelRequestCapture(pi, ${JSON.stringify({ requestsPath: p.requests, activeTurnPath: p.active, captureStatePath: p.state, allowedRefsPath: p.allowed, acknowledgementsPath: p.acks, runtime: runtimeIdentity })}, async () => { throw new Error("capture rejected"); });`;
	await writeFile(join(dir, "capture.ts"), source);
}
