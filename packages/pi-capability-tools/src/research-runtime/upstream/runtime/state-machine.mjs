// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { ConcurrencySemaphore } from "./concurrency.mjs";
import { generateRunId } from "./ids.mjs";
import { JsonlLogger } from "./logger.mjs";
import { createReportStyle } from "./report-styles.mjs";
import { ResearchDraft } from "./research-draft.mjs";
import { executeResearchRound } from "./research-round.mjs";
export class ResearchStateMachine {
    searchFn;
    scraper;
    profileResolver;
    defaultReportStyle;
    logger;
    artifactsDir;
    searchCred;
    style;
    phaseStartMs = 0;
    constructor(ctx){
        this.ports = ctx.ports;
        this.searchFn = ctx.searchFn;
        this.scraper = ctx.scraper;
        this.profileResolver = ctx.profileResolver;
        this.artifactsDir = ctx.artifactsDir ?? defaultArtifactsDir();
        this.searchCred = ctx.searchCred;
        this.logger = ctx.logger;
        this.defaultReportStyle = ctx.defaultReportStyle ?? "narrative";
    }
    static init(plan, resolver, runId) {
        const profile = resolver.resolve(plan.profile);
        return {
            phase: "searching",
            runId: runId ?? generateRunId(),
            currentDepth: 0,
            totalDepth: profile.depth,
            allFindings: [],
            allVisitedUrls: [],
            draft: new ResearchDraft(),
            reportPath: "",
            searchCalls: 0,
            scrapeCalls: 0,
            startedAt: Date.now(),
            softLimitTriggered: false,
            profile
        };
    }
    async next(snapshot, plan, agentResponse) {
        if (!this.logger) {
            const logsDir = join(this.artifactsDir, "..", "logs");
            mkdirSync(logsDir, {
                recursive: true
            });
            this.logger = new JsonlLogger(snapshot.runId, join(logsDir, `${snapshot.runId}.log`));
        }
        if (!snapshot.profile) {
            snapshot.profile = this.profileResolver.resolve(plan.profile);
            snapshot.totalDepth = snapshot.profile.depth;
        }
        this.phaseStartMs = Date.now();
        if (!this.style) {
            this.style = createReportStyle(plan.reportStyle ?? this.defaultReportStyle) ?? createReportStyle("narrative");
        }
        switch(snapshot.phase){
            case "searching":
                return this.doSearching(snapshot, plan);
            case "extracting":
                return this.doExtracting(snapshot, plan);
            case "questioning":
                return this.doQuestioning(snapshot, plan, agentResponse);
            case "drafting":
                return this.doDrafting(snapshot, plan, agentResponse);
            case "saving":
                return this.doSaving(snapshot, agentResponse);
            case "done":
                return {
                    phase: "done",
                    snapshot
                };
            default:
                throw new Error("Invalid research phase");
        }
    }
    checkSoftLimits(snapshot) {
        const prof = snapshot.profile;
        const elapsed = (Date.now() - snapshot.startedAt) / 1000;
        const maxCalls = prof.maxSearchCalls ?? 0;
        const maxSec = prof.maxElapsedSeconds ?? 0;
        if (!snapshot.softLimitTriggered && (maxCalls > 0 && snapshot.searchCalls >= maxCalls || maxSec > 0 && elapsed >= maxSec)) {
            snapshot.softLimitTriggered = true;
            this.logger?.event("soft_limit_triggered", {
                searchCalls: snapshot.searchCalls,
                maxSearchCalls: maxCalls,
                elapsedSeconds: Math.round(elapsed),
                maxElapsedSeconds: maxSec
            });
        }
    }
    async doSearching(snapshot, plan) {
        if (this.ports?.searching) return this.ports.searching(snapshot, plan);
        const prof = snapshot.profile;
        const questions = snapshot.pendingQuestions && snapshot.pendingQuestions.length > 0 ? snapshot.pendingQuestions : plan.researchQuestions;
        snapshot.pendingQuestions = undefined;
        const maxResultsPerQuery = snapshot.softLimitTriggered ? 2 : 3;
        const breadth = snapshot.softLimitTriggered ? Math.min(2, prof.breadth) : prof.breadth;
        const meta = plan.questionMetadata;
        const isIterationZero = snapshot.currentDepth === 0;
        const sorted = meta && isIterationZero ? [
            ...questions
        ].sort((a, b)=>{
            const ia = meta[a]?.importance;
            const ib = meta[b]?.importance;
            const rank = (i)=>i === "critical" ? 0 : i === "important" ? 1 : 2;
            return rank(ia) - rank(ib);
        }) : questions;
        const activeQuestions = sorted.slice(0, breadth);
        const semaphore = new ConcurrencySemaphore(prof.concurrency);
        const rawEngines = plan.engines.length > 0 ? plan.engines : [
            "duckduckgo"
        ];
        const allowlist = plan.enabledEngines;
        const engines = allowlist && allowlist.length > 0 ? rawEngines.filter((e)=>allowlist.includes(e)) : rawEngines;
        if (engines.length === 0) engines.push("duckduckgo");
        const round = await executeResearchRound({
            searchFn: this.searchFn,
            scraper: this.scraper,
            logger: this.logger,
            activeQuestions,
            maxResultsPerQuery,
            engines: engines,
            semaphore,
            visitedUrls: new Set(snapshot.allVisitedUrls),
            artifactsDir: this.artifactsDir,
            runId: snapshot.runId,
            currentDepth: snapshot.currentDepth,
            searchCred: this.searchCred
        });
        snapshot.searchCalls += round.searchCalls;
        snapshot.scrapeCalls += round.scrapeCalls;
        const nextDepth = snapshot.currentDepth + 1;
        const nextSnapshot = {
            ...snapshot,
            phase: "extracting",
            currentDepth: nextDepth,
            allVisitedUrls: [
                ...round.newVisitedUrls
            ]
        };
        this.checkSoftLimits(nextSnapshot);
        const style = this.style;
        let inject = style.buildExtractionPrompt(round.searchResults, round.scrapedPages, nextDepth, snapshot.totalDepth);
        if (meta && activeQuestions.some((q)=>meta[q])) {
            const metaContext = activeQuestions.filter((q)=>meta[q]).map((q)=>{
                const m = meta[q];
                return `- **${q}** — source: ${m.source}, confidence: ${m.confidence}, importance: ${m.importance}${m.debatableFact ? `, ⚠ debatable: ${m.debatableFact}` : ""}`;
            }).join("\n");
            inject = `### Question Metadata\n\nResearch questions with expected provenance and confidence. Use this to weight findings appropriately.\n\n${metaContext}\n\n---\n\n${inject}`;
        }
        this.logger?.event("phase_changed", {
            from: "searching",
            to: "extracting",
            depth: nextDepth
        });
        if (this.logLevel === "verbose") {
            this.logger?.event("verbose_questions", {
                depth: nextDepth,
                questions: activeQuestions
            });
        }
        this.logger?.event("inject_sent", {
            type: "extraction",
            length: inject.length,
            depth: nextDepth
        });
        return {
            phase: "extracting",
            snapshot: nextSnapshot,
            inject
        };
    }
    doExtracting(snapshot, plan) {
        if (this.ports?.extracting) return this.ports.extracting(snapshot, plan);
        const nextPhase = phaseRouter(snapshot);
        if (nextPhase === "questioning") {
            return this.doQuestioningInject(snapshot, plan);
        }
        this.logger?.event("deepening_skipped", {
            reason: snapshot.softLimitTriggered ? "soft_limit" : "depth_reached",
            currentDepth: snapshot.currentDepth,
            totalDepth: snapshot.totalDepth
        });
        return this.doDraftingInject(snapshot, plan);
    }
    doQuestioningInject(snapshot, plan) {
        const inject = this.style.buildQuestioningPrompt(plan, snapshot.currentDepth, snapshot.totalDepth);
        this.logger?.event("phase_changed", {
            from: "extracting",
            to: "questioning",
            depth: snapshot.currentDepth
        });
        this.logger?.event("inject_sent", {
            type: "deepening",
            length: inject.length,
            depth: snapshot.currentDepth
        });
        return {
            phase: "questioning",
            snapshot: {
                ...snapshot,
                phase: "questioning"
            },
            inject
        };
    }
    doDraftingInject(snapshot, plan) {
        const inject = this.style.buildDraftingPrompt(plan, snapshot.allFindings);
        this.logger?.event("phase_changed", {
            from: "extracting",
            to: "drafting",
            depth: snapshot.currentDepth
        });
        this.logger?.event("inject_sent", {
            type: "drafting",
            length: inject.length
        });
        return {
            phase: "drafting",
            snapshot: {
                ...snapshot,
                phase: "drafting"
            },
            inject
        };
    }
    async doQuestioning(snapshot, plan, parsedResponse) {
        if (this.ports?.questioning) return this.ports.questioning(snapshot, plan, parsedResponse);
        if (parsedResponse) {
            const questions = this.extractQuestions(parsedResponse);
            snapshot.pendingQuestions = questions.length > 0 ? questions : plan.researchQuestions;
        } else {
            snapshot.pendingQuestions = plan.researchQuestions;
        }
        const searchSnapshot = {
            ...snapshot,
            phase: "searching"
        };
        return this.doSearching(searchSnapshot, plan);
    }
    extractQuestions(text) {
        const lines = text.split("\n");
        const questions = [];
        for (const line of lines){
            const match = line.match(/^\s*\d+[.)]\s+(.+)/);
            if (match && match[1].trim().length > 10) {
                questions.push(match[1].trim());
            }
        }
        return questions;
    }
    doDrafting(snapshot, plan, parsedResponse) {
        if (this.ports?.drafting) return this.ports.drafting(snapshot, plan, parsedResponse);
        const reportText = parsedResponse ?? "";
        this.logger?.event("drafting_extracted", {
            textLength: reportText.length,
            agentResponseType: "string"
        });
        if (!reportText || reportText.length < 40) {
            const inject = this.style.buildDraftingPrompt(plan, snapshot.allFindings);
            this.logger?.event("drafting_retry", {
                reason: "empty_response",
                length: reportText?.length ?? 0
            });
            return {
                phase: "drafting",
                snapshot: {
                    ...snapshot,
                    phase: "drafting"
                },
                inject: `⚠️ No report text in your response.\n\n**Write the report as your response text. Do NOT call run_research or any other tools.** After you write the complete report, then call run_research.\n\n${inject}`
            };
        }
        snapshot.draft.set(reportText);
        this.logger?.event("phase_changed", {
            from: "drafting",
            to: "saving"
        });
        return {
            phase: "saving",
            snapshot: {
                ...snapshot,
                phase: "saving"
            }
        };
    }
    doSaving(snapshot, _parsedResponse) {
        if (this.ports?.saving) return this.ports.saving(snapshot, _parsedResponse);
        if (!snapshot.draft.isReady()) {
            this.logger?.event("saving_blocked", {
                reason: "empty_draft",
                draftLength: snapshot.draft.get().length
            });
            return {
                phase: "saving",
                snapshot
            };
        }
        this.logger?.event("phase_changed", {
            from: "saving",
            to: "done",
            draftLength: snapshot.draft.get().length
        });
        return {
            phase: "done",
            snapshot: {
                ...snapshot,
                phase: "done"
            }
        };
    }
    async resume(stateBlob, rawAgentResponse, plan) {
        const parsedResponse = extractTextContent(rawAgentResponse) || undefined;
        const draftEncoded = stateBlob.draftEncoded;
        const snapshot = stateBlob;
        snapshot.draft = draftEncoded ? ResearchDraft.decode(draftEncoded) : new ResearchDraft();
        return this.next(snapshot, plan, parsedResponse);
    }
}
function phaseRouter(snapshot) {
    const shouldDeepen = !snapshot.softLimitTriggered && snapshot.currentDepth < snapshot.totalDepth;
    return shouldDeepen ? "questioning" : "drafting";
}
function extractTextContent(agentResponse) {
    if (!agentResponse) return "";
    if (typeof agentResponse === "string") {
        return agentResponse.replace(/<tool_calls>[\s\S]*?<\/tool_calls>/g, "").trim();
    }
    if (Array.isArray(agentResponse)) {
        return agentResponse.filter((b)=>b.type === "text" && b.text).map((b)=>b.text).join("\n");
    }
    return "";
}
const stateMachineDir = dirname(fileURLToPath(import.meta.url));
const defaultArtifactsDir = ()=>join(stateMachineDir, "..", "..", "deep-research", "artifacts");
