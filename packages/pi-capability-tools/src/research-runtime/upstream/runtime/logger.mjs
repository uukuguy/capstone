// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
export class JsonlLogger {
    path;
    runId;
    constructor(runId, path){
        this.runId = runId;
        this.path = path;
        mkdirSync(dirname(path), {
            recursive: true
        });
    }
    event(type, data) {
        const entry = {
            ts: new Date().toISOString(),
            runId: this.runId,
            type,
            ...data
        };
        const line = JSON.stringify(entry) + "\n";
        appendFileSync(this.path, line, "utf-8");
    }
}
