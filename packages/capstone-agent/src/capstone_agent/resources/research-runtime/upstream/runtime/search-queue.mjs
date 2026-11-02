// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
const DDG_MIN_DELAY_MS = 2000;
const DDG_MAX_DELAY_MS = 4000;
export function buildSearchQueue(questions, engines) {
    const now = new Date().toISOString();
    const queue = [];
    const engineDelay = {};
    for(let i = 0; i < questions.length; i++){
        const engine = engines[i % engines.length];
        const prevDelay = engineDelay[engine] ?? 0;
        const needsStagger = engine === "duckduckgo" || engine === "searxng";
        const scheduledDelayMs = needsStagger ? prevDelay : 0;
        queue.push({
            question: questions[i],
            engine,
            scheduledDelayMs,
            timestamp: now
        });
        if (needsStagger) {
            const jitter = DDG_MIN_DELAY_MS + Math.floor(Math.random() * (DDG_MAX_DELAY_MS - DDG_MIN_DELAY_MS + 1));
            engineDelay[engine] = (engineDelay[engine] ?? 0) + jitter;
        }
    }
    return queue;
}
export function saveQueue(queue, path) {
    mkdirSync(dirname(path), {
        recursive: true
    });
    writeFileSync(path, JSON.stringify(queue, null, 2), "utf-8");
}
