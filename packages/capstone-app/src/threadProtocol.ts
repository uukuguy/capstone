export type RunState = 'created' | 'open' | 'closing' | 'closed' | 'failed'
export type AttemptPhase = 'created' | 'accepted' | 'running' | 'waiting' | 'committing' |
  'cancelled' | 'interrupted' | 'completed' | 'failed'

export type RunSnapshot = { runId: string; state: RunState }
export type ModelContextSnapshot = {
  id: string; modelId: string; modelRevision: string; implementationFamily: string; selectionRevision: string
}
export type AttemptSnapshot = {
  turnId: string; attemptId: string; phase: AttemptPhase; targetModelContextId: string
}
export type ThreadSnapshot = {
  threadId: string
  run: RunSnapshot
  activeModelContext: ModelContextSnapshot
  activeGridPageId: string
  currentAttempt: AttemptSnapshot | null
  lastEventSeq: number
  baseEventSeq: number
  toDocument: () => Record<string, unknown>
}

export type EventEnvelope = {
  eventId: string
  eventSeq: number
  eventType: string
  eventVersion: number
  threadId: string
  runId: string
  turnId?: string
  attemptId?: string
  modelContextId?: string
  selectionRevision?: string
  occurredAt: string
  visibility: 'public' | 'diagnostic'
  payload: Record<string, unknown>
}
export type EventPage = {
  threadId: string
  afterEventSeq: number
  nextEventSeq: number
  hasMore: boolean
  events: EventEnvelope[]
  toDocument: () => Record<string, unknown>
}

export type CommandReceipt = {
  commandId: string
  idempotencyKey: string
  threadId: string
  runId?: string
  status: 'accepted' | 'rejected' | 'pending'
  acceptedEventSeq?: number
  rejection?: string
  target?: Record<string, unknown>
  toDocument: () => Record<string, unknown>
}

export class ThreadProtocolError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ThreadProtocolError'
  }
}

const identifierPattern = /^[a-z][a-z0-9_-]{0,63}$/
const runStates = new Set<RunState>(['created', 'open', 'closing', 'closed', 'failed'])
const attemptPhases = new Set<AttemptPhase>([
  'created', 'accepted', 'running', 'waiting', 'committing',
  'cancelled', 'interrupted', 'completed', 'failed',
])

function object(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new ThreadProtocolError(`${name} must be an object`)
  }
  return value as Record<string, unknown>
}

function fields(value: Record<string, unknown>, allowed: ReadonlySet<string>, name: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key))
  if (unknown.length) throw new ThreadProtocolError(`${name} has unknown field: ${unknown.sort().join(', ')}`)
}

function required(value: Record<string, unknown>, keys: readonly string[], name: string): void {
  const missing = keys.filter((key) => !(key in value))
  if (missing.length) throw new ThreadProtocolError(`${name} is missing field: ${missing.join(', ')}`)
}

function identifier(value: unknown, name: string): string {
  if (typeof value !== 'string' || !identifierPattern.test(value)) throw new ThreadProtocolError(`${name} is invalid`)
  return value
}

function text(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value) throw new ThreadProtocolError(`${name} is invalid`)
  return value
}

function sequence(value: unknown, name: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw new ThreadProtocolError(`${name} is invalid`)
  return value as number
}

function jsonValue(value: unknown, name: string): void {
  try { JSON.stringify(value) } catch { throw new ThreadProtocolError(`${name} is not JSON`) }
}

function timestamp(value: unknown, name: string): string {
  const result = text(value, name)
  if (Number.isNaN(Date.parse(result))) throw new ThreadProtocolError(`${name} is invalid`)
  return result
}

function optionalIdentifier(value: unknown, name: string): string | undefined {
  return value === undefined || value === null ? undefined : identifier(value, name)
}

function parseRun(value: unknown): RunSnapshot {
  const document = object(value, 'run')
  fields(document, new Set(['run_id', 'state']), 'run')
  required(document, ['run_id', 'state'], 'run')
  const state = text(document.state, 'run.state') as RunState
  if (!runStates.has(state)) throw new ThreadProtocolError('run.state is invalid')
  return { runId: identifier(document.run_id, 'run.run_id'), state }
}

function parseContext(value: unknown): ModelContextSnapshot {
  const document = object(value, 'active_model_context')
  const keys = ['id', 'model_id', 'model_revision', 'implementation_family', 'selection_revision']
  fields(document, new Set(keys), 'active_model_context')
  required(document, keys, 'active_model_context')
  return {
    id: identifier(document.id, 'active_model_context.id'),
    modelId: identifier(document.model_id, 'active_model_context.model_id'),
    modelRevision: text(document.model_revision, 'active_model_context.model_revision'),
    implementationFamily: identifier(document.implementation_family, 'active_model_context.implementation_family'),
    selectionRevision: text(document.selection_revision, 'active_model_context.selection_revision'),
  }
}

function parseAttempt(value: unknown): AttemptSnapshot {
  const document = object(value, 'current_attempt')
  const keys = ['turn_id', 'attempt_id', 'phase', 'target_model_context_id']
  fields(document, new Set(keys), 'current_attempt')
  required(document, keys, 'current_attempt')
  const phase = text(document.phase, 'current_attempt.phase') as AttemptPhase
  if (!attemptPhases.has(phase)) throw new ThreadProtocolError('current_attempt.phase is invalid')
  return {
    turnId: identifier(document.turn_id, 'current_attempt.turn_id'),
    attemptId: identifier(document.attempt_id, 'current_attempt.attempt_id'),
    phase,
    targetModelContextId: identifier(document.target_model_context_id, 'current_attempt.target_model_context_id'),
  }
}

function snapshotDocument(snapshot: Omit<ThreadSnapshot, 'toDocument'>): Record<string, unknown> {
  return {
    schema: 'capstone-thread-snapshot/1',
    thread_id: snapshot.threadId,
    run: { run_id: snapshot.run.runId, state: snapshot.run.state },
    active_model_context: {
      id: snapshot.activeModelContext.id,
      model_id: snapshot.activeModelContext.modelId,
      model_revision: snapshot.activeModelContext.modelRevision,
      implementation_family: snapshot.activeModelContext.implementationFamily,
      selection_revision: snapshot.activeModelContext.selectionRevision,
    },
    active_grid_page_id: snapshot.activeGridPageId,
    current_attempt: snapshot.currentAttempt ? {
      turn_id: snapshot.currentAttempt.turnId,
      attempt_id: snapshot.currentAttempt.attemptId,
      phase: snapshot.currentAttempt.phase,
      target_model_context_id: snapshot.currentAttempt.targetModelContextId,
    } : null,
    last_event_seq: snapshot.lastEventSeq,
    base_event_seq: snapshot.baseEventSeq,
  }
}

export function parseThreadSnapshot(value: unknown): ThreadSnapshot {
  const document = object(value, 'snapshot')
  const keys = ['schema', 'thread_id', 'run', 'active_model_context', 'active_grid_page_id', 'current_attempt', 'last_event_seq', 'base_event_seq']
  fields(document, new Set(keys), 'snapshot')
  required(document, keys, 'snapshot')
  if (document.schema !== 'capstone-thread-snapshot/1') throw new ThreadProtocolError('snapshot.schema is invalid')
  const lastEventSeq = sequence(document.last_event_seq, 'snapshot.last_event_seq')
  const baseEventSeq = sequence(document.base_event_seq, 'snapshot.base_event_seq')
  if (baseEventSeq > lastEventSeq) throw new ThreadProtocolError('snapshot base_event_seq exceeds last_event_seq')
  const activeModelContext = parseContext(document.active_model_context)
  const currentAttempt = document.current_attempt === null ? null : parseAttempt(document.current_attempt)
  if (currentAttempt && currentAttempt.targetModelContextId !== activeModelContext.id) {
    throw new ThreadProtocolError('current_attempt target context does not match active context')
  }
  const snapshot = {
    threadId: identifier(document.thread_id, 'snapshot.thread_id'),
    run: parseRun(document.run),
    activeModelContext,
    activeGridPageId: identifier(document.active_grid_page_id, 'snapshot.active_grid_page_id'),
    currentAttempt,
    lastEventSeq,
    baseEventSeq,
  }
  return { ...snapshot, toDocument: () => snapshotDocument(snapshot) }
}

function parseEvent(value: unknown): EventEnvelope {
  const document = object(value, 'event')
  const keys = ['event_id', 'event_seq', 'event_type', 'event_version', 'thread_id', 'run_id', 'turn_id', 'attempt_id', 'model_context_id', 'selection_revision', 'occurred_at', 'visibility', 'payload']
  fields(document, new Set(keys), 'event')
  required(document, ['event_id', 'event_seq', 'event_type', 'event_version', 'thread_id', 'run_id', 'occurred_at', 'visibility', 'payload'], 'event')
  if (!Number.isSafeInteger(document.event_version) || (document.event_version as number) < 1) throw new ThreadProtocolError('event.event_version is invalid')
  if (document.visibility !== 'public' && document.visibility !== 'diagnostic') throw new ThreadProtocolError('event.visibility is invalid')
  const payload = object(document.payload, 'event.payload')
  jsonValue(payload, 'event.payload')
  return {
    eventId: identifier(document.event_id, 'event.event_id'), eventSeq: sequence(document.event_seq, 'event.event_seq'),
    eventType: text(document.event_type, 'event.event_type'), eventVersion: document.event_version as number,
    threadId: identifier(document.thread_id, 'event.thread_id'), runId: identifier(document.run_id, 'event.run_id'),
    turnId: optionalIdentifier(document.turn_id, 'event.turn_id'), attemptId: optionalIdentifier(document.attempt_id, 'event.attempt_id'),
    modelContextId: optionalIdentifier(document.model_context_id, 'event.model_context_id'),
    selectionRevision: document.selection_revision == null ? undefined : text(document.selection_revision, 'event.selection_revision'),
    occurredAt: timestamp(document.occurred_at, 'event.occurred_at'), visibility: document.visibility,
    payload,
  }
}

export function parseEventPage(value: unknown, expectedAfterSeq?: number): EventPage {
  const document = object(value, 'event_page')
  const keys = ['schema', 'thread_id', 'after_event_seq', 'next_event_seq', 'has_more', 'events']
  fields(document, new Set(keys), 'event_page')
  required(document, keys, 'event_page')
  if (document.schema !== 'capstone-thread-events/1') throw new ThreadProtocolError('event_page.schema is invalid')
  const afterEventSeq = sequence(document.after_event_seq, 'event_page.after_event_seq')
  if (expectedAfterSeq !== undefined && afterEventSeq !== expectedAfterSeq) throw new ThreadProtocolError('event page does not start at expected cursor')
  if (typeof document.has_more !== 'boolean' || !Array.isArray(document.events)) throw new ThreadProtocolError('event_page pagination is invalid')
  const threadId = identifier(document.thread_id, 'event_page.thread_id')
  const events = document.events.map(parseEvent)
  let expectedSeq = afterEventSeq + 1
  for (const event of events) {
    if (event.threadId !== threadId) throw new ThreadProtocolError('event thread_id does not match page')
    if (event.eventSeq !== expectedSeq) throw new ThreadProtocolError('event page is not contiguous')
    expectedSeq += 1
  }
  const nextEventSeq = sequence(document.next_event_seq, 'event_page.next_event_seq')
  if (nextEventSeq !== expectedSeq - 1) throw new ThreadProtocolError('event_page.next_event_seq is invalid')
  const page = { threadId, afterEventSeq, nextEventSeq, hasMore: document.has_more, events }
  return { ...page, toDocument: () => ({
    schema: 'capstone-thread-events/1', thread_id: page.threadId,
    after_event_seq: page.afterEventSeq, next_event_seq: page.nextEventSeq,
    has_more: page.hasMore, events: page.events.map((event) => ({
      event_id: event.eventId, event_seq: event.eventSeq, event_type: event.eventType,
      event_version: event.eventVersion, thread_id: event.threadId, run_id: event.runId,
      ...(event.turnId ? { turn_id: event.turnId } : {}), ...(event.attemptId ? { attempt_id: event.attemptId } : {}),
      ...(event.modelContextId ? { model_context_id: event.modelContextId } : {}),
      ...(event.selectionRevision ? { selection_revision: event.selectionRevision } : {}),
      occurred_at: event.occurredAt, visibility: event.visibility, payload: event.payload,
    })),
  }) }
}

export function parseCommandReceipt(value: unknown): CommandReceipt {
  const document = object(value, 'receipt')
  const keys = ['schema', 'command_id', 'idempotency_key', 'thread_id', 'run_id', 'status', 'accepted_event_seq', 'rejection', 'target']
  fields(document, new Set(keys), 'receipt')
  required(document, ['schema', 'command_id', 'idempotency_key', 'thread_id', 'status'], 'receipt')
  if (document.schema !== 'capstone-command-receipt/1') throw new ThreadProtocolError('receipt.schema is invalid')
  if (document.status !== 'accepted' && document.status !== 'rejected' && document.status !== 'pending') throw new ThreadProtocolError('receipt.status is invalid')
  if (document.target !== undefined && document.target !== null) jsonValue(object(document.target, 'receipt.target'), 'receipt.target')
  const receipt = {
    commandId: identifier(document.command_id, 'receipt.command_id'), idempotencyKey: identifier(document.idempotency_key, 'receipt.idempotency_key'),
    threadId: identifier(document.thread_id, 'receipt.thread_id'), runId: optionalIdentifier(document.run_id, 'receipt.run_id'),
    status: document.status, acceptedEventSeq: document.accepted_event_seq == null ? undefined : sequence(document.accepted_event_seq, 'receipt.accepted_event_seq'),
    rejection: document.rejection == null ? undefined : text(document.rejection, 'receipt.rejection'),
    target: document.target == null ? undefined : object(document.target, 'receipt.target'),
  } as CommandReceipt
  return { ...receipt, toDocument: () => ({
    schema: 'capstone-command-receipt/1', command_id: receipt.commandId,
    idempotency_key: receipt.idempotencyKey, thread_id: receipt.threadId,
    ...(receipt.runId ? { run_id: receipt.runId } : {}), status: receipt.status,
    ...(receipt.acceptedEventSeq !== undefined ? { accepted_event_seq: receipt.acceptedEventSeq } : {}),
    ...(receipt.rejection ? { rejection: receipt.rejection } : {}), ...(receipt.target ? { target: receipt.target } : {}),
  }) }
}
