// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
export class ConcurrencySemaphore {
    limit;
    running = 0;
    queue = [];
    constructor(limit){
        this.limit = limit;
    }
    async run(fn) {
        while(this.running >= this.limit){
            await new Promise((resolve)=>this.queue.push(resolve));
        }
        this.running++;
        try {
            return await fn();
        } finally{
            this.running--;
            this.queue.shift()?.();
        }
    }
}
