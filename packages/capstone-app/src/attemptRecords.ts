import {exceedsCapacity} from './applicationCapacity'
import { parseContext, parseEventEnvelope, type EventEnvelope, type ModelContextSnapshot } from './threadProtocol'

export interface AttemptRecords {
  threadId: string
  attemptId: string
  instruction: string
  modelContext: ModelContextSnapshot | null
  events: EventEnvelope[]
  nextAfter: number
  hasMore: boolean
}

/** Bind record reads to the selected historical task, never the current model. */
export function parseAttemptRecords(value: unknown, threadId: string, attemptId: string, after: number): AttemptRecords {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('任务记录格式无效')
  const page = value as Record<string, unknown>
  if (page.schema !== 'capstone-attempt-records/1' || page.thread_id !== threadId || page.attempt_id !== attemptId) {
    throw new Error('任务记录身份不一致')
  }
  if (typeof page.instruction !== 'string' || exceedsCapacity(page.instruction.length,'input_text_chars') ||
      !Array.isArray(page.events) || exceedsCapacity(page.events.length,'native_record_count') || typeof page.has_more !== 'boolean' ||
      !Number.isSafeInteger(after) || after < 0 || !Number.isSafeInteger(page.next_after)) throw new Error('任务记录分页无效')
  const modelContext = page.model_context === null ? null : parseContext(page.model_context)
  const events = page.events.map(parseEventEnvelope)
  let cursor = after
  for (const event of events) {
    if (event.threadId !== threadId || event.attemptId !== attemptId || event.eventSeq <= cursor ||
        (modelContext && event.modelContextId && event.modelContextId !== modelContext.id)) throw new Error('任务记录来源不一致')
    cursor = event.eventSeq
  }
  if (page.next_after !== cursor || (page.has_more && events.length === 0)) throw new Error('任务记录游标无效')
  return { threadId, attemptId, instruction: page.instruction, modelContext, events, nextAfter: cursor, hasMore: page.has_more }
}
