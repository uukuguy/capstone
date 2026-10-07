import type { ThreadMessageLike } from '@assistant-ui/react'
import type { EventEnvelope } from './threadProtocol'

/** Client presentation only: never a command, answer or authority record. */
export type ThreadSystemNotice = {
  id: string
  afterEventSeq: number
  text: string
  tone: 'info' | 'error'
  instruction?: string
  action?: 'reconnect' | 'resync'
}

export function upsertSystemNotice(items: readonly ThreadSystemNotice[], notice: ThreadSystemNotice): ThreadSystemNotice[] {
  const index = items.findIndex((item) => item.id === notice.id)
  if (index < 0) return [...items, notice].slice(-100)
  const next = [...items]
  next[index] = { ...notice, afterEventSeq: items[index].afterEventSeq }
  return next
}

export function projectSystemNotices(messages: readonly ThreadMessageLike[], events: readonly EventEnvelope[], notices: readonly ThreadSystemNotice[], historyAtLatest = true): ThreadMessageLike[] {
  const first = events[0]?.eventSeq ?? 0
  const last = events.at(-1)?.eventSeq ?? 0
  const eventSequences = new Map(events.map((event) => [event.eventId, event.eventSeq]))
  const attemptSequences = new Map<string, number>()
  for (const event of events) {
    const key = event.attemptId || event.turnId
    if (key && !attemptSequences.has(key)) attemptSequences.set(key, event.eventSeq)
  }
  const rows = messages.map((message, index) => {
    const custom = message.metadata?.custom
    const seq = typeof custom?.eventId === 'string' ? eventSequences.get(custom.eventId)
      : typeof custom?.attemptId === 'string' ? attemptSequences.get(custom.attemptId) : undefined
    return { message, seq: seq ?? 0, order: index }
  })
  const durable = events.flatMap((event): ThreadSystemNotice[] => {
    if (event.eventType === 'selection_activated') return [{ id: event.eventId, afterEventSeq: event.eventSeq, text: '电网计算分析工具选择已生效。', tone: 'info' }]
    if (!['model_context_activated', 'model_context_reopened'].includes(event.eventType)) return []
    const context = event.payload.model_context as Record<string, unknown> | undefined
    const model = typeof context?.model_id === 'string' ? context.model_id : ''
    return [{ id: event.eventId, afterEventSeq: event.eventSeq, text: `${event.eventType === 'model_context_reopened' ? '已重新打开' : '已打开'}电网模型${model ? ` ${model}` : ''}。`, tone: 'info' }]
  })
  for (const notice of [...durable, ...notices]) {
    // Local notices remain in this mounted workspace. Show only the loaded
    // history range; a historical page must not acquire later local outcomes.
    // At the live edge the cursor can follow a diagnostic-only event, so the
    // last public event is not an upper bound for a local recovery notice.
    if (events.length && (notice.afterEventSeq < first - 1 || (!historyAtLatest && notice.afterEventSeq > last))) continue
    rows.push({ seq: notice.afterEventSeq, order: messages.length + rows.length,
      message: { id: `system-${notice.id}`, role: 'assistant', content: notice.text,
        status: { type: 'complete', reason: 'stop' }, metadata: { custom: { systemNotice: notice } } } })
  }
  return rows.sort((a, b) => a.seq - b.seq || a.order - b.order).map((row) => row.message)
}
