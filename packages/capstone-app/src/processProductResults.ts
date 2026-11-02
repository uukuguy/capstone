import {exceedsCapacity} from './applicationCapacity'
import type { AttemptRecordReader } from './AttemptRecordPanel'
import { ResultProjectionDelivery } from './resultProjectionDelivery'
import { parseResultProjection, type ResultProjection } from './threadProtocol'

/** Recover admitted projections from the original attempt, including chunked delivery. */
export async function readProcessProductResults(threadId:string, attemptId:string, read:AttemptRecordReader, signal?:AbortSignal):Promise<ResultProjection[]> {
  const delivery=new ResultProjectionDelivery()
  let after=0
  const results:ResultProjection[]=[]
  for (;;) {
    signal?.throwIfAborted()
    const page=await read(attemptId,after)
    signal?.throwIfAborted()
    if(page.threadId!==threadId || page.attemptId!==attemptId || page.hasMore && page.nextAfter<=after)throw new Error('结果来源不一致')
    for(const event of page.events){
      if(event.threadId!==threadId || event.attemptId!==attemptId)throw new Error('结果来源不一致')
      delivery.accept(event)
      if(!['attempt_completed','attempt_failed','attempt_cancelled','attempt_interrupted'].includes(event.eventType))continue
      const documents=delivery.complete(event) ?? event.payload.result_projections
      if(documents===undefined)continue
      if(!Array.isArray(documents) || exceedsCapacity(documents.length,'ui_result_projection_count'))throw new Error('结果目录无效')
      for(const document of documents){
        const result=parseResultProjection(document)
        const admission=event.payload.admission as Record<string,unknown> | undefined
        if(result.threadId!==threadId || result.attemptId!==attemptId || result.runId!==event.runId || result.turnId!==event.turnId || result.modelContextId!==event.modelContextId
          || admission?.mode!=='authority_backed' || admission.assurance!=='lineage_verified'
          || !Array.isArray(event.payload.result_refs) || !event.payload.result_refs.includes(result.resultRef)
          || !Array.isArray(event.payload.evidence_refs) || result.evidenceRefs.some(ref=>!(event.payload.evidence_refs as unknown[]).includes(ref)))throw new Error('结果来源不一致')
        results.push(result)
      }
    }
    if(!page.hasMore)return results
    after=page.nextAfter
  }
}
