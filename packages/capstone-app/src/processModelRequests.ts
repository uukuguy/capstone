import type { EventEnvelope } from './threadProtocol'
import type { ProcessModelCall } from './ProcessCallTrace'
import {isExecutionLifecycleStep} from './executionLifecycle'

/** Only public parent request boundaries. Diagnostic text is never reasoning copy. */
export function projectProcessModelRequests(events: readonly EventEnvelope[], attemptId: string): ProcessModelCall[] {
  const calls: ProcessModelCall[] = []
  let pending: ProcessModelCall | undefined
  let turn: ProcessModelCall | undefined
  let openingText=''
  const thinkingEvents=new Set<string>()
  const native = events.some(event=>event.attemptId===attemptId&&event.visibility==='public'&&['turn_route_selected','turn_plan_created'].includes(event.eventType)&&event.payload.source==='native_conversation')
  for (const event of events) {
    if (event.attemptId !== attemptId) continue
    if(pending&&event.visibility==='public'&&event.eventType==='assistant_thinking_delta'&&typeof event.payload.text==='string'){
      if(!thinkingEvents.has(event.eventId)){
        thinkingEvents.add(event.eventId)
        pending.thinking=(pending.thinking??'')+event.payload.text
        pending.thinkingStartedAt??=event.occurredAt
        pending.thinkingEndedAt=event.occurredAt
      }
      continue
    }
    if(pending&&event.eventType==='assistant_process_delta'&&typeof event.payload.text==='string'){
      if(pending.thinking)pending.thinkingSettled=true
      openingText=(openingText+event.payload.text).slice(0,512)
      const line=openingText.split(/\r?\n/)[0].trim()
      if(line.startsWith('//'))pending.intent=line.slice(2).trim().slice(0,160)
      continue
    }
    if(event.visibility!=='public')continue
    if (['attempt_completed','attempt_failed','attempt_cancelled','attempt_interrupted'].includes(event.eventType)) {
      if(pending){
        if(['attempt_cancelled','attempt_interrupted'].includes(event.eventType))pending.stopReason = 'aborted'
        pending.settled = true
      }
      pending = undefined
      turn = undefined
      continue
    }
    if(native&&turn?.toolAssociation==='turn'&&event.eventType==='runtime_event'&&event.payload.native_type==='tool_execution_start'){
      const id=event.payload.tool_call_id
      if(typeof id==='string'&&id&&!turn.toolCallIds?.includes(id))turn.toolCallIds=[...(turn.toolCallIds??[]),id]
    }
    if (event.eventType !== 'runtime_action') continue
    const step=event.payload.task_step
    if (step && typeof step === 'object' && 'id' in step && typeof step.id === 'string' && isExecutionLifecycleStep(step.id)) continue
    if (event.payload.phase === 'started') {
      if(pending)pending.settled=true
      pending = { id: event.eventId, number: calls.length + 1, ms: 0, startedAt: event.occurredAt }
      calls.push(pending)
      turn=pending
      openingText=''
    } else if (event.payload.phase === 'response_completed' && pending) {
      // The host explicitly distinguishes text-only responses from tool requests.
      if(event.payload.response_kind==='text')pending.toolCallIds=[]
      if(native&&event.payload.response_kind==='tools'){
        pending.toolCallIds=[]
        pending.toolAssociation='turn'
      }
      if (event.payload.response_kind === 'error' || event.payload.response_kind === 'aborted') pending.stopReason = event.payload.response_kind
      if(typeof event.payload.error_code==='string'&&/^[a-z][a-z0-9_]{0,127}$/.test(event.payload.error_code))pending.errorCode=event.payload.error_code
      if(typeof event.payload.error_status==='number'&&Number.isInteger(event.payload.error_status)&&event.payload.error_status>=400&&event.payload.error_status<=599)pending.errorStatus=event.payload.error_status
      const elapsed = Date.parse(event.occurredAt) - Date.parse(pending.startedAt!)
      if (Number.isFinite(elapsed) && elapsed >= 0) {
        pending.finishedAt = event.occurredAt
        pending.ms = elapsed
        pending.settled = true
      }
      pending = undefined
    } else if (event.payload.phase === 'response_completed') {
      // A response without its opening boundary cannot extend the prior turn.
      turn = undefined
    } else if (['completed', 'interrupted'].includes(String(event.payload.phase))) {
      // A task terminal boundary cannot measure the preceding model request.
      if (pending && event.payload.phase === 'interrupted') {
        pending.stopReason = 'aborted'
        pending.settled = true
      }
      pending = undefined
      turn = undefined
    }
  }
  return calls
}
