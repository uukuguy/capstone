import type { ThreadMessageLike } from '@assistant-ui/react'
import { projectAssistantMessages } from './CapstoneAssistantThread'
import type { EventEnvelope } from './threadProtocol'
import type { WorkRecord } from './threadWorkProtocol'
import type {ThinkingPreview} from './thinkingPreview'
import {projectSystemNotices} from './threadSystemNotices'

/** Presentation filtering follows admission of the full Thread sequence. */
export function projectWorkConversation(events: readonly EventEnvelope[], work?: WorkRecord, allWorks: readonly WorkRecord[] = [], legacyOnly = false, previews:readonly ThinkingPreview[]=[]) {
  const owners = new Map<string, string | null>()
  const identity = (event: EventEnvelope) => event.attemptId ? `attempt:${event.attemptId}` : event.turnId ? `turn:${event.turnId}` : undefined
  for (const row of allWorks) if (row.latestAttemptId) owners.set(`attempt:${row.latestAttemptId}`, row.workId)
  for (const event of events) {
    const key = identity(event)
    if (!key) continue
    if (typeof event.payload.work_id === 'string') owners.set(key, event.payload.work_id)
    else if (event.eventType === 'command_accepted' && event.eventVersion === 1 && !owners.has(key)) owners.set(key, null)
  }
  let hasUnattributedHistory = false
  const selected = events.filter(event => {
    const key = identity(event)
    const owner = typeof event.payload.work_id === 'string' ? event.payload.work_id : key ? owners.get(key) : undefined
    if (owner === null || legacyOnly) return true
    if (owner !== undefined) return owner === work?.workId
    if (key) { hasUnattributedHistory = true; return false }
    return true
  })
  const sequences = new Map(selected.map(event => [event.eventId, event.eventSeq]))
  const attempts = new Map<string, number>()
  for (const event of selected) if (event.attemptId && !attempts.has(event.attemptId)) attempts.set(event.attemptId, event.eventSeq)
  const presentation = selected.map(event => event.eventType === 'command_accepted' && event.payload.kind === 'send_message'
    ? {...event, payload: {...event.payload, kind: 'send_auto'}} : event)
  const goalStepEvents = new Map(presentation.flatMap(event => {
    if (event.eventType !== 'command_accepted' || !event.attemptId) return []
    const row = event.payload.work as {goal_plan?: {step_index?: number; plan?: {steps?: {instruction: string}[]}}} | undefined
    const index = row?.goal_plan?.step_index ?? 0
    const steps = row?.goal_plan?.plan?.steps
    const input = event.payload.payload as {text?: string} | undefined
    if (typeof index !== 'number' || !steps?.[index] || steps[index].instruction !== input?.text) return []
    return [[event.eventId, `${index + 1}/${steps.length}`] as const]
  }))
  const rows = projectAssistantMessages(presentation,[],previews).filter(message => work?.conversationMode || message.role !== 'user'
    || goalStepEvents.has(String(message.metadata?.custom?.eventId))
    || !selected.some(event => event.eventId === message.metadata?.custom?.eventId && work !== undefined && event.payload.work_id === work.workId))
    .map((message, index) => {
      const custom = message.metadata?.custom
      const seq = typeof custom?.eventId === 'string' ? sequences.get(custom.eventId) : typeof custom?.attemptId === 'string' ? attempts.get(custom.attemptId) : undefined
      const goalStep = message.role === 'user' ? goalStepEvents.get(String(custom?.eventId)) : undefined
      return { message: goalStep ? {...message, metadata: {custom: {...custom, goalStep}}} : message, seq: seq ?? 0, order: index }
    })
  for (const [index, text] of (work?.conversationMode ? [] : work?.messages || []).entries()) {
    const source = selected.find(event => {
      const row = event.payload.work as Record<string, unknown> | undefined
      return event.payload.work_id === work?.workId && Array.isArray(row?.messages) && row.messages.length > index
    })
    rows.push({ message: { id: `${work!.workId}-message-${index}`, role: 'user', content: work?.goalMode && index === 0 ? `Goal 目标 · ${text}` : text,
      metadata: { custom: { workId: work!.workId, ...(source ? { sentAt: source.occurredAt } : {}) } } },
      seq: source?.eventSeq ?? 0, order: rows.length })
  }
  const messages=rows.sort((a,b)=>a.seq-b.seq||a.order-b.order).map(item=>item.message) as ThreadMessageLike[]
  return { events: selected, hasUnattributedHistory, messages:projectSystemNotices(messages,selected,[]) }
}
