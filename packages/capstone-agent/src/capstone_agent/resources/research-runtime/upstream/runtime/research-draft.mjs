// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
import { deflateSync, inflateSync } from "node:zlib";
export class ResearchDraft {
    text;
    constructor(text){
        this.text = text ?? "";
    }
    set(text) {
        this.text = text;
    }
    get() {
        return this.text;
    }
    isReady() {
        return this.text.length >= 40;
    }
    encode() {
        if (!this.isReady()) return undefined;
        const buf = deflateSync(Buffer.from(this.text, "utf-8"));
        return buf.toString("base64url");
    }
    static decode(encoded) {
        try {
            const buf = Buffer.from(encoded, "base64url");
            const inflated = inflateSync(buf);
            return new ResearchDraft(inflated.toString("utf-8"));
        } catch  {
            return new ResearchDraft();
        }
    }
}
