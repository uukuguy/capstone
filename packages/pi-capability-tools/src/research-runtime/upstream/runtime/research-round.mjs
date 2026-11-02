// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
import { join } from "node:path";
import { buildSearchQueue, saveQueue } from "./search-queue.mjs";
export async function executeResearchRound(params) {
    const { searchFn, scraper, logger, activeQuestions, maxResultsPerQuery, engines, semaphore, visitedUrls, artifactsDir, runId, currentDepth, searchCred } = params;
    if (activeQuestions.length === 0 || engines.length === 0) {
        return {
            searchResults: [],
            scrapedPages: [],
            newVisitedUrls: visitedUrls,
            searchCalls: 0,
            scrapeCalls: 0
        };
    }
    let searchCalls = 0;
    let scrapeCalls = 0;
    const queue = buildSearchQueue(activeQuestions, engines);
    if (artifactsDir) {
        try {
            saveQueue(queue, join(artifactsDir, `queue-${runId}-d${currentDepth}.json`));
            logger?.event("queue_saved", {
                depth: currentDepth,
                entries: queue.length,
                engines: engines.join(",")
            });
        } catch  {}
    }
    const searchResults = await Promise.all(activeQuestions.map((question)=>semaphore.run(async ()=>{
            const startMs = Date.now();
            const results = await searchFn(question, maxResultsPerQuery, engines, {
                logger,
                credentials: searchCred
            });
            logger?.event("search_executed", {
                query: question,
                resultCount: results.length,
                elapsedMs: Date.now() - startMs,
                depth: currentDepth
            });
            searchCalls++;
            return {
                question,
                results
            };
        })));
    const newVisited = new Set(visitedUrls);
    const urlsToScrape = [];
    for (const { results } of searchResults){
        for (const r of results.slice(0, 2)){
            if (!newVisited.has(r.url)) {
                urlsToScrape.push(r.url);
                newVisited.add(r.url);
            }
        }
    }
    const scrapedResults = await Promise.all(urlsToScrape.map((url)=>semaphore.run(async ()=>{
            try {
                const startMs = Date.now();
                const page = await scraper.scrape(url);
                logger?.event("scrape_executed", {
                    url,
                    title: page.title,
                    bytes: page.content.length,
                    elapsedMs: Date.now() - startMs,
                    depth: currentDepth
                });
                scrapeCalls++;
                return page;
            } catch (err) {
                logger?.event("scrape_failed", {
                    url,
                    error: err instanceof Error ? err.message : String(err),
                    depth: currentDepth
                });
                return null;
            }
        })));
    const scrapedPages = scrapedResults.filter((p)=>p !== null);
    return {
        searchResults,
        scrapedPages,
        newVisitedUrls: newVisited,
        searchCalls,
        scrapeCalls
    };
}
