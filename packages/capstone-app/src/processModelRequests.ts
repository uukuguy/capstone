import type { EventEnvelope } from './threadProtocol'
import type { ProcessModelCall } from './ProcessCallTrace'
import {isExecutionLifecycleStep} from './executionLifecycle'

/** Only public parent request boundaries. Diagnostic text is never reasoning copy. */
export function projectProcessModelRequests(events: readonly EventEnvelope[], attemptId: string): ProcessModelCall[] {
  const calls: ProcessModelCall[] = []
  let pending: ProcessModelCall | undefined
  for (const event of events) {
    if (event.attemptId !== attemptId || event.visibility !== 'public') continue
    if (['attempt_cancelled','attempt_interrupted'].includes(event.eventType) && pending) {
      pending.stopReason = 'aborted'
      pending.settled = true
      pending = undefined
    }
    if (event.eventType !== 'runtime_action') continue
    const step=event.payload.task_step
    if (step && typeof step === 'object' && 'id' in step && typeof step.id === 'string' && isExecutionLifecycleStep(step.id)) continue
    if (event.payload.phase === 'started' && !pending) {
      pending = { id: event.eventId, number: calls.length + 1, ms: 0, startedAt: event.occurredAt }
      calls.push(pending)
    } else if (event.payload.phase === 'response_completed' && pending) {
      // The host explicitly distinguishes text-only responses from tool requests.
      if(event.payload.response_kind==='text')pending.toolCallIds=[]
      if (event.payload.response_kind === 'error' || event.payload.response_kind === 'aborted') pending.stopReason = event.payload.response_kind
      const elapsed = Date.parse(event.occurredAt) - Date.parse(pending.startedAt!)
      if (Number.isFinite(elapsed) && elapsed >= 0) {
        pending.finishedAt = event.occurredAt
        pending.ms = elapsed
        pending.settled = true
      }
      pending = undefined
    } else if (['completed', 'interrupted'].includes(String(event.payload.phase))) {
      // A task terminal boundary cannot measure the preceding model request.
      if (pending && event.payload.phase === 'interrupted') {
        pending.stopReason = 'aborted'
        pending.settled = true
      }
      pending = undefined
    }
  }
  return calls
}
