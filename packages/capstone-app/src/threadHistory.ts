import { parseEventEnvelope, type EventEnvelope } from './threadProtocol'

export type ThreadHistoryPage = {
  threadId: string; beforeEventSeq: number; nextBeforeEventSeq: number
  hasMore: boolean; events: EventEnvelope[]
}

export function parseThreadHistoryPage(value: unknown, threadId: string, before?: number): ThreadHistoryPage {
  if (!value || typeof value !== 'object') throw new Error('消息历史无效')
  const body = value as Record<string, unknown>
  const start = body.before_event_seq as number
  const next = body.next_before_event_seq as number
  if (body.schema !== 'capstone-thread-history/1' || body.thread_id !== threadId
      || !Number.isSafeInteger(start) || start < 1 || (before !== undefined && start !== before)
      || !Number.isSafeInteger(next) || next < 1 || next > start
      || typeof body.has_more !== 'boolean' || !Array.isArray(body.events) || body.events.length > 256) throw new Error('消息历史游标无效')
  const events = body.events.map(parseEventEnvelope)
  let previous = next - 1
  for (const event of events) {
    if (event.threadId !== threadId || event.visibility !== 'public' || event.eventSeq <= previous || event.eventSeq >= start) throw new Error('消息历史顺序无效')
    previous = event.eventSeq
  }
  if ((events.length > 0 && events[0].eventSeq !== next) || (body.has_more && (!events.length || next >= start))) throw new Error('消息历史无法继续加载')
  return { threadId, beforeEventSeq: start, nextBeforeEventSeq: next, hasMore: body.has_more, events }
}

export function parseNetworkContextEvents(value: unknown, threadId: string, contextId: string): EventEnvelope[] {
  if (!value || typeof value !== 'object') throw new Error('电网历史投影无效')
  const body = value as Record<string, unknown>
  if (body.schema !== 'capstone-thread-network-events/1' || body.thread_id !== threadId
      || body.model_context_id !== contextId || !Array.isArray(body.events) || body.events.length > 4) throw new Error('电网历史投影身份无效')
  const events = body.events.map(parseEventEnvelope)
  if (events.some((event) => event.threadId !== threadId || event.modelContextId !== contextId || event.visibility !== 'public'
    || !['network_diagram', 'network_layer', 'network_layer_unavailable', 'attempt_completed'].includes(event.eventType))) throw new Error('电网历史投影事件无效')
  return events
}
