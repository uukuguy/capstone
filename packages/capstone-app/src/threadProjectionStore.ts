import { parseThreadSnapshot, type CommandReceipt, type EventEnvelope, type EventPage, type ModelContextSnapshot, type ThreadSnapshot } from './threadProtocol'
import { parseNetworkDiagram, parseNetworkView } from './networkValidation'
import type { DiagramNetworkView, NetworkDiagram } from './types'
import type { ThreadCatalog } from './threadCatalog'
import {
  CapstoneThreadClient, type ThreadCommand, type ThreadTransport, type ThreadTransportState,
} from './threadClient'

export type ThreadConnection = ThreadTransportState | 'connecting'

export type PendingThreadCommand = {
  command: ThreadCommand
  receipt?: CommandReceipt
}

export type ThreadGridPage = {
  pageId: string
  context: ModelContextSnapshot
  networkView: DiagramNetworkView | null
}

export type ThreadNetworkTask = {
  attemptId: string
  eventSeq: number
  pageId: string
  context: ModelContextSnapshot
  view: DiagramNetworkView
}

export type ThreadProjectionState = {
  connection: ThreadConnection
  snapshot: ThreadSnapshot | null
  eventSeq: number
  resyncRequired: boolean
  pendingCommands: readonly PendingThreadCommand[]
  viewedGridPageId: string | null
  catalog: ThreadCatalog | null
  networkView: DiagramNetworkView | null
  gridPages: readonly ThreadGridPage[]
}

export type ThreadFixtureDocument = {
  snapshot: unknown
  events: unknown
  assertions?: { transport_state?: unknown }
  local_view?: { viewed_grid_page_id?: unknown; draft?: unknown; replay?: unknown }
  catalog?: unknown
}

function fixtureConnection(fixture: ThreadFixtureDocument): ThreadTransportState {
  const value = fixture.assertions?.transport_state
  if (value === 'reconnecting' || value === 'resync_required' || value === 'offline') return value
  return 'live'
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value as Record<string, unknown>
}

export function instructionOrdinal(events: readonly EventEnvelope[], attemptId: string | undefined): number | undefined {
  const attempts = new Map<string, number>()
  const turns = new Map<string, number>()
  let next = 0
  for (const event of events) {
    if (event.eventType !== 'command_accepted' || !event.attemptId) continue
    const kind = event.payload.kind
    if (['send_auto', 'send_ordinary', 'send_professional'].includes(String(kind))) {
      const ordinal = attempts.get(event.attemptId) || (event.turnId && turns.get(event.turnId)) || ++next
      attempts.set(event.attemptId, ordinal)
      if (event.turnId) turns.set(event.turnId, ordinal)
    } else if (kind === 'retry_new_attempt') {
      const prior = record(event.payload.payload).retry_of
      const ordinal = (event.turnId && turns.get(event.turnId)) || (typeof prior === 'string' && attempts.get(prior))
      if (ordinal) attempts.set(event.attemptId, ordinal)
    }
  }
  return attemptId ? attempts.get(attemptId) : undefined
}

function resyncSnapshot(error: unknown): ThreadSnapshot | null {
  const body = record(record(error).body)
  if (body.error !== 'resync_required' || !('snapshot' in body)) return null
  try {
    return parseThreadSnapshot(body.snapshot)
  } catch {
    return null
  }
}

function requiresResync(error: unknown): boolean {
  if (resyncSnapshot(error)) return true
  return error instanceof Error && (
    error.message.includes('contiguous') || error.message.includes('does not match')
  )
}

async function readSnapshotEvents(
  client: CapstoneThreadClient,
  snapshot: ThreadSnapshot,
  intern: (event: EventEnvelope) => EventEnvelope = (event) => event,
): Promise<EventEnvelope[]> {
  const events: EventEnvelope[] = []
  let cursor = snapshot.baseEventSeq
  while (cursor < snapshot.lastEventSeq) {
    const page = await client.readAfter(snapshot.threadId, cursor)
    if (page.threadId !== snapshot.threadId) throw new Error('event page thread does not match snapshot')
    for (const event of page.events) {
      // `readAfter` may observe events appended after the snapshot was
      // captured. They are outside this restore target and belong to the
      // subsequent catch-up pass; do not turn that normal race into offline.
      if (event.eventSeq > snapshot.lastEventSeq) break
      if (event.eventSeq !== cursor + 1) throw new Error('event history is not contiguous')
      events.push(intern(event))
      cursor = event.eventSeq
    }
    if (page.nextEventSeq < cursor) {
      throw new Error('event history cursor does not match snapshot')
    }
    if (cursor < snapshot.lastEventSeq && page.nextEventSeq > snapshot.lastEventSeq) {
      throw new Error('event history is incomplete')
    }
    if (cursor < snapshot.lastEventSeq) cursor = page.nextEventSeq
    if (!page.hasMore && cursor < snapshot.lastEventSeq) throw new Error('event history is incomplete')
    if (page.events.length === 0 && cursor < snapshot.lastEventSeq) throw new Error('event history made no progress')
  }
  return events
}

/** A checked-fixture transport for the first Web/TUI projection prototype. */
export function createFixtureTransport(fixture: ThreadFixtureDocument): ThreadTransport {
  const receipts = new Map<string, Record<string, unknown>>()
  const snapshot = record(fixture.snapshot)
  const run = record(snapshot.run)
  const eventDocument = record(fixture.events)
  const eventLog = Array.isArray(eventDocument.events) ? [...eventDocument.events] : []
  let nextEventSeq = typeof eventDocument.next_event_seq === 'number'
    ? eventDocument.next_event_seq
    : eventLog.reduce((maximum, event) => Math.max(maximum, record(event).event_seq as number || 0), 0)

  function readEventDocument(afterEventSeq: number): Record<string, unknown> {
    return {
      ...eventDocument,
      after_event_seq: afterEventSeq,
      next_event_seq: nextEventSeq,
      has_more: false,
      events: eventLog.filter((event) => {
        const seq = record(event).event_seq
        return typeof seq === 'number' && seq > afterEventSeq
      }),
    }
  }

  function appendMessageProjection(command: ThreadCommand): number | undefined {
    if (!['send_auto', 'send_ordinary', 'send_professional'].includes(command.kind)) return undefined
    const text = typeof command.payload.text === 'string' ? command.payload.text : ''
    if (!text) return undefined
    const token = `${command.command_id}_${nextEventSeq + 1}`
    const attemptId = `attempt_fixture_${token}`
    const turnId = `turn_fixture_${token}`
    const context = record(snapshot.active_model_context)
    const base = {
      thread_id: command.thread_id,
      run_id: command.run_id || run.run_id,
      turn_id: turnId,
      attempt_id: attemptId,
      model_context_id: context.id,
      selection_revision: context.selection_revision,
      occurred_at: new Date().toISOString(),
      visibility: 'public',
      event_version: 1,
    }
    const append = (event_type: string, payload: Record<string, unknown>) => {
      nextEventSeq += 1
      eventLog.push({
        ...base, event_id: `evt_fixture_${nextEventSeq}`, event_seq: nextEventSeq,
        event_type, payload,
      })
    }
    append('command_accepted', {
      command_id: command.command_id, kind: command.kind, payload: command.payload,
    })
    append('attempt_started', { attempt_id: attemptId })
    append('assistant_text_delta', { text: `Fixture 已接收${command.kind === 'send_professional' ? '专业请求' : '自动指令'}：${text}` })
    append('attempt_completed', { attempt_id: attemptId })
    return nextEventSeq - 3
  }

  return {
    connectionState: fixtureConnection(fixture),
    getSnapshot: async () => fixture.snapshot,
    getCatalog: async () => fixture.catalog ?? { schema: 'capstone-thread-catalog/1', models: [], profiles: [] },
    readEvents: async (_threadId, afterEventSeq) => readEventDocument(afterEventSeq),
    sendCommand: async (command) => {
      const existing = receipts.get(command.idempotency_key)
      if (existing) return existing
      const acceptedEventSeq = appendMessageProjection(command)
      const receipt = {
        schema: 'capstone-command-receipt/1',
        command_id: command.command_id,
        idempotency_key: command.idempotency_key,
        thread_id: command.thread_id,
        ...(typeof run.run_id === 'string' ? { run_id: run.run_id } : {}),
        status: 'accepted',
        ...(acceptedEventSeq !== undefined ? { accepted_event_seq: acceptedEventSeq } : {}),
      }
      receipts.set(command.idempotency_key, receipt)
      return receipt
    },
  }
}

export class ThreadProjectionStore {
  private current: ThreadProjectionState = {
    connection: 'offline', snapshot: null, eventSeq: 0, resyncRequired: false,
    pendingCommands: [], viewedGridPageId: null, catalog: null,
    networkView: null, gridPages: [],
  }

  private loadedThreadId: string | null = null
  private loadGeneration = 0
  private readonly eventLog: EventEnvelope[] = []
  private readonly networkDiagrams = new Map<string, NetworkDiagram>()
  private readonly sharedDiagrams = new Map<string, NetworkDiagram>()
  private readonly networkViews = new Map<string, DiagramNetworkView>()
  private readonly taskViews = new Map<string, ThreadNetworkTask>()
  private readonly contextPages = new Map<string, ThreadGridPage>()
  private readonly diagramAttempts = new Map<string, string | undefined>()
  private readonly listeners = new Set<() => void>()

  constructor(private readonly client: CapstoneThreadClient) {}

  get state(): ThreadProjectionState {
    return this.current
  }

  get publicEvents(): readonly EventEnvelope[] {
    return this.eventLog.filter((event) => event.visibility === 'public')
  }

  get networkTasks(): readonly ThreadNetworkTask[] {
    return [...this.taskViews.values()]
  }

  get canStreamEvents(): boolean {
    return this.client.supportsEventStream
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify(): void {
    for (const listener of this.listeners) listener()
  }

  async load(threadId: string): Promise<void> {
    const generation = ++this.loadGeneration
    const sameThread = this.loadedThreadId === threadId
    const previousView = this.loadedThreadId === threadId ? this.current.viewedGridPageId : null
    this.current = {
      ...this.current,
      connection: 'connecting', snapshot: sameThread ? this.current.snapshot : null,
      eventSeq: sameThread ? this.current.eventSeq : 0, resyncRequired: false,
      pendingCommands: sameThread ? this.current.pendingCommands : [],
    }
    this.notify()
    try {
      const snapshot = await this.client.load(threadId)
      if (generation !== this.loadGeneration) return
      let catalog: ThreadCatalog | null = null
      try {
        catalog = await this.client.catalog(threadId)
      } catch {
        // A legacy API may not expose the optional catalog yet. The active
        // snapshot remains authoritative and the Thread stays usable.
      }
      const connection = this.client.connectionState
      // A snapshot with an un-compacted history must restore that history
      // before the UI becomes live. Otherwise the model state would look
      // current while the conversation is silently truncated.
      const restoredDiagrams = new Map<string, NetworkDiagram>()
      const restoredEvents = await readSnapshotEvents(this.client, snapshot,
        (event) => this.internDiagramEvent(event, restoredDiagrams))
      // StrictMode and reconnects can overlap loads. A superseded response
      // must not replace the live cursor or erase events already received.
      if (generation !== this.loadGeneration) return
      this.sharedDiagrams.clear()
      for (const [key, diagram] of restoredDiagrams) this.sharedDiagrams.set(key, diagram)
      this.current = {
        ...this.current,
        connection,
        snapshot,
        eventSeq: snapshot.lastEventSeq,
        resyncRequired: connection === 'resync_required',
        viewedGridPageId: previousView ?? snapshot.activeGridPageId,
        catalog,
      }
      this.eventLog.length = 0
      this.eventLog.push(...restoredEvents)
      this.networkDiagrams.clear()
      this.networkViews.clear()
      this.taskViews.clear()
      this.contextPages.clear()
      this.diagramAttempts.clear()
      this.current = { ...this.current, networkView: null, gridPages: [] }
      // Discover the latest Context for each model page before replaying
      // topology. A reopened Context must never inherit an older diagram.
      for (const event of restoredEvents) this.applyGridPageHistory(event, snapshot)
      this.rememberGridPage(snapshot.activeGridPageId, snapshot.activeModelContext)
      for (const event of restoredEvents) this.applyNetworkProjection(event, snapshot)
      this.notify()
      this.loadedThreadId = threadId
    } catch (error) {
      if (generation !== this.loadGeneration) return
      const snapshot = resyncSnapshot(error)
      this.current = {
        ...this.current,
        connection: snapshot ? 'resync_required' : 'offline',
        resyncRequired: Boolean(snapshot),
        ...(snapshot ? { snapshot, eventSeq: snapshot.lastEventSeq } : {}),
      }
      this.notify()
      throw error
    }
  }

  async catchUp(): Promise<EventPage> {
    const generation = this.loadGeneration
    if (this.current.resyncRequired || this.current.connection === 'resync_required') {
      throw new Error('thread is resync_required')
    }
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    try {
      const page = await this.client.readAfter(snapshot.threadId, this.current.eventSeq)
      if (generation !== this.loadGeneration) return page
      if (page.threadId !== snapshot.threadId) throw new Error('event page thread does not match snapshot')
      this.applyPage(page)
      this.notify()
      return page
    } catch (error) {
      if (generation !== this.loadGeneration) throw error
      const snapshot = resyncSnapshot(error)
      this.current = {
        ...this.current,
        connection: requiresResync(error) ? 'resync_required' : 'reconnecting',
        resyncRequired: requiresResync(error),
        ...(snapshot ? { snapshot, eventSeq: snapshot.lastEventSeq } : {}),
      }
      this.notify()
      throw error
    }
  }

  async catchUpThrough(eventSeq: number): Promise<void> {
    const generation = this.loadGeneration
    let more = true
    while (more || this.current.eventSeq < eventSeq) {
      const previous = this.current.eventSeq
      const page = await this.catchUp()
      if (generation !== this.loadGeneration) throw new Error('thread projection changed during synchronization')
      more = page.hasMore
      if (this.current.eventSeq === previous && (more || this.current.eventSeq < eventSeq)) {
        throw new Error('accepted command events are not yet available; reconnect before retrying')
      }
    }
  }

  async consumeEvents(signal?: AbortSignal): Promise<void> {
    const generation = this.loadGeneration
    if (this.current.resyncRequired || this.current.connection === 'resync_required') {
      throw new Error('thread is resync_required')
    }
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    try {
      for await (const event of this.client.events(snapshot.threadId, this.current.eventSeq, signal)) {
        if (generation !== this.loadGeneration) return
        this.applyEvent(event)
      }
    } catch (error) {
      if (generation !== this.loadGeneration) return
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      const snapshot = resyncSnapshot(error)
      this.current = {
        ...this.current,
        connection: requiresResync(error) ? 'resync_required' : 'reconnecting',
        resyncRequired: requiresResync(error),
        ...(snapshot ? {
          snapshot, eventSeq: snapshot.lastEventSeq,
          viewedGridPageId: snapshot.activeGridPageId,
        } : {}),
      }
      if (snapshot) this.eventLog.length = 0
      this.notify()
      throw error
    }
  }

  viewGridPage(pageId: string): void {
    if (!pageId) throw new Error('grid page id is required')
    this.current = { ...this.current, viewedGridPageId: pageId }
    this.notify()
  }

  returnLiveGridPage(): void {
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    this.current = { ...this.current, viewedGridPageId: snapshot.activeGridPageId }
    this.notify()
  }

  async dispatch(command: ThreadCommand): Promise<CommandReceipt> {
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    if (this.current.resyncRequired || this.current.connection !== 'live') {
      throw new Error(`thread is ${this.current.connection}`)
    }
    if (command.thread_id !== snapshot.threadId) throw new Error('command thread does not match snapshot')
    const existing = this.current.pendingCommands.find((entry) => entry.command.idempotency_key === command.idempotency_key)
    if (!existing && this.current.pendingCommands.some((entry) => !entry.receipt)) {
      throw new Error('previous command receipt is unresolved; 请重新连接核对发送结果。')
    }
    if (existing) {
      const sameCommand = existing.command.command_id === command.command_id
        && existing.command.thread_id === command.thread_id
        && existing.command.run_id === command.run_id
        && existing.command.kind === command.kind
        && existing.command.expected_event_seq === command.expected_event_seq
        && JSON.stringify(existing.command.payload) === JSON.stringify(command.payload)
      if (!sameCommand) throw new Error('idempotency key is already bound to another command')
    }
    if (!existing) {
      this.current = {
        ...this.current,
        pendingCommands: [...this.current.pendingCommands, { command }],
      }
      this.notify()
    }
    try {
      const receipt = await this.client.send(command)
      if (receipt.threadId !== snapshot.threadId) throw new Error('receipt thread does not match snapshot')
      if (receipt.commandId !== command.command_id) throw new Error('receipt command does not match command')
      if (receipt.idempotencyKey !== command.idempotency_key) throw new Error('receipt idempotency key does not match command')
      this.current = {
        ...this.current,
        pendingCommands: this.current.pendingCommands.map((entry) => (
          entry.command.idempotency_key === command.idempotency_key ? { ...entry, receipt } : entry
        )),
      }
      this.notify()
      // The receipt is authoritative even if reading its events fails. Keep
      // reconnect state, but do not tell the Composer that an accepted send failed.
      if (!this.canStreamEvents) {
        try { await this.catchUp() } catch { /* catchUp records the recovery state */ }
      }
      return receipt
    } catch (error) {
      this.current = { ...this.current, connection: 'reconnecting' }
      this.notify()
      throw error
    }
  }

  private applyPage(page: EventPage): void {
    for (const event of page.events) this.applyEvent(event)
  }

  private applyEvent(event: EventEnvelope): void {
    const snapshot = this.current.snapshot
    // Catch-up and SSE can deliver the same admitted event. Keep one copy
    // without moving the cursor backwards or hiding a conflicting event.
    if (snapshot && event.threadId === snapshot.threadId && event.eventSeq <= this.current.eventSeq) {
      const previous = this.eventLog.find((item) => item.eventSeq === event.eventSeq)
      if (previous?.eventId === event.eventId && JSON.stringify(previous) === JSON.stringify(event)) return
      throw new Error('duplicate event does not match admitted history')
    }
    if (!snapshot || event.threadId !== snapshot.threadId || event.eventSeq !== this.current.eventSeq + 1) {
      throw new Error('event stream is not contiguous')
    }
    event = this.internDiagramEvent(event)
    let currentAttempt = snapshot.currentAttempt
    const previousActivePage = snapshot.activeGridPageId
    let viewedGridPageId = this.current.viewedGridPageId
    const document = snapshot.toDocument()
    const payload = record(event.payload)
    if (event.eventType === 'model_context_change_pending') {
      document.pending_model_switch = {
        command_id: payload.command_id,
        model_id: payload.model_id,
        model_revision: payload.model_revision,
        implementation_family: payload.implementation_family,
        ...(payload.reason === 'explicit_reopen' ? { reason: payload.reason } : {}),
        ...(typeof payload.fresh_context_reason === 'string' ? { fresh_context_reason: payload.fresh_context_reason } : {}),
        selection: payload.selection,
      }
      delete document.pending_selection
    } else if (event.eventType === 'selection_change_pending') {
      document.pending_selection = { command_id: payload.command_id, selection: payload.selection }
    } else if (event.eventType === 'model_context_activated' || event.eventType === 'model_context_reopened' || event.eventType === 'model_context_reverted') {
      this.current = { ...this.current, networkView: null }
      const context = payload.model_context ?? payload.restored_context
      if (context) document.active_model_context = context
      const page = payload.active_grid_page_id ?? payload.restored_grid_page_id
      if (typeof page === 'string') document.active_grid_page_id = page
      delete document.pending_model_switch
      delete document.pending_selection
      if (viewedGridPageId === previousActivePage && typeof page === 'string') viewedGridPageId = page
    } else if (event.eventType === 'selection_activated') {
      const activeContext = record(document.active_model_context)
      activeContext.selection_revision = event.selectionRevision
      activeContext.enabled_profiles = payload.selection
      document.active_model_context = activeContext
      delete document.pending_selection
    } else if (event.eventType === 'selection_reverted') {
      const activeContext = record(document.active_model_context)
      activeContext.selection_revision = event.selectionRevision
      activeContext.enabled_profiles = payload.restored_selection
      document.active_model_context = activeContext
      delete document.pending_selection
    }
    if (event.eventType === 'attempt_completed' && Array.isArray(payload.result_projections)) {
      const existing = Array.isArray(document.result_projections) ? document.result_projections : []
      document.result_projections = [...existing, ...payload.result_projections].slice(-64)
    }
    const identity = event.turnId && event.attemptId && event.modelContextId
      ? { turnId: event.turnId, attemptId: event.attemptId, targetModelContextId: event.modelContextId }
      : null
    if (event.eventType === 'command_accepted' && identity) {
      currentAttempt = { ...identity, phase: 'accepted' }
    } else if (event.eventType === 'attempt_started' && identity) {
      currentAttempt = { ...identity, phase: 'running' }
    } else if (event.eventType === 'attempt_completed' || event.eventType === 'attempt_failed' ||
      event.eventType === 'attempt_cancelled' || event.eventType === 'attempt_interrupted') {
      if (!currentAttempt || !event.attemptId || currentAttempt.attemptId === event.attemptId) currentAttempt = null
    }
    const projected = parseThreadSnapshot({
      ...document,
      current_attempt: currentAttempt ? {
        turn_id: currentAttempt.turnId, attempt_id: currentAttempt.attemptId,
        phase: currentAttempt.phase, target_model_context_id: currentAttempt.targetModelContextId,
      } : null,
      last_event_seq: event.eventSeq,
    })
    this.current = { ...this.current, snapshot: projected, eventSeq: event.eventSeq, viewedGridPageId }
    this.applyGridPageHistory(event, projected)
    this.rememberGridPage(projected.activeGridPageId, projected.activeModelContext)
    const activeView = this.current.gridPages.find((page) => page.pageId === projected.activeGridPageId)?.networkView ?? null
    this.current = { ...this.current, networkView: activeView }
    this.applyNetworkProjection(event, projected)
    this.eventLog.push(event)
    this.notify()
  }

  private internDiagramEvent(event: EventEnvelope, diagrams = this.sharedDiagrams): EventEnvelope {
    if (event.eventType !== 'network_diagram') return event
    const diagram = parseNetworkDiagram(event.payload.diagram)
    if (!diagram) return event
    const key = `${diagram.model.id}:${diagram.model.revision}:${diagram.ref}`
    const existing = diagrams.get(key)
    if (existing && JSON.stringify(existing) !== JSON.stringify(diagram)) {
      throw new Error('diagram identity does not match admitted history; 请重新同步电网图。')
    }
    if (!existing) diagrams.set(key, diagram)
    return { ...event, payload: { ...event.payload, diagram: existing || diagram } }
  }

  private rememberGridPage(pageId: string, context: ModelContextSnapshot): void {
    const existing = this.current.gridPages.find((page) => page.pageId === pageId)
    const page: ThreadGridPage = {
      pageId, context,
      networkView: (() => {
        const view = this.networkViews.get(context.id)
        return view?.diagram.model.id === context.modelId && view.diagram.model.revision === context.modelRevision ? view : null
      })(),
    }
    this.contextPages.set(context.id, page)
    this.current = { ...this.current, gridPages: existing
      ? this.current.gridPages.map((item) => item.pageId === pageId ? page : item)
      : [...this.current.gridPages, page] }
  }

  private applyGridPageHistory(event: EventEnvelope, snapshot: ThreadSnapshot): void {
    if (event.visibility !== 'public') return
    if (!['model_context_activated', 'model_context_reopened', 'model_context_reverted'].includes(event.eventType)) return
    const payload = record(event.payload)
    for (const [pageId, context] of [
      [payload.previous_grid_page_id, payload.previous_context],
      [payload.active_grid_page_id ?? payload.restored_grid_page_id, payload.model_context ?? payload.restored_context],
    ]) {
      if (typeof pageId !== 'string' || !context) continue
      try {
        const parsed = parseThreadSnapshot({
          ...snapshot.toDocument(), active_grid_page_id: pageId,
          active_model_context: context, current_attempt: null,
        })
        this.rememberGridPage(parsed.activeGridPageId, parsed.activeModelContext)
      } catch {
        // An incomplete history entry does not supply a usable page Context.
      }
    }
  }

  private applyNetworkProjection(event: EventEnvelope, snapshot: ThreadSnapshot, completedRefs: string[] = []): void {
    if (event.visibility !== 'public') return
    if (event.eventType === 'attempt_completed' && event.attemptId) {
      const layer = this.eventLog.slice().reverse().find((item) => item.eventType === 'network_layer' &&
        item.attemptId === event.attemptId && item.modelContextId === event.modelContextId)
      const refs = record(event.payload).result_refs
      if (layer) this.applyNetworkProjection(layer, snapshot, Array.isArray(refs) ? refs.filter((ref): ref is string => typeof ref === 'string') : [])
      return
    }
    const page = event.modelContextId ? this.contextPages.get(event.modelContextId) : undefined
    if (!page) return
    const context = page.context
    const setView = (networkView: DiagramNetworkView | null) => {
      if (networkView) this.networkViews.set(context.id, networkView)
      else this.networkViews.delete(context.id)
      this.current = { ...this.current,
        gridPages: this.current.gridPages.map((item) => item.pageId === page.pageId && item.context.id === context.id ? { ...item, networkView } : item),
        ...(context.id === snapshot.activeModelContext.id ? { networkView } : {}),
      }
    }
    const payload = record(event.payload)
    if (event.eventType === 'network_diagram') {
      const diagram = parseNetworkDiagram(payload.diagram)
      if (!diagram || diagram.model.id !== context.modelId || diagram.model.revision !== context.modelRevision) {
        this.networkDiagrams.delete(context.id)
        setView(null)
        return
      }
      this.networkDiagrams.set(context.id, diagram)
      this.diagramAttempts.set(context.id, event.attemptId)
      setView(null)
      return
    }
    if (event.eventType === 'network_layer') {
      const diagram = this.networkDiagrams.get(context.id)
      if (!diagram || typeof payload.ordinal !== 'number' || this.diagramAttempts.get(context.id) !== event.attemptId) return
      const view = parseNetworkView({
        schema: 'capstone-network-view/2.0',
        ordinal: payload.ordinal,
        diagram,
        layer: payload.layer,
      }, payload.ordinal, [
        ...completedRefs,
        ...(snapshot.resultProjections || []).filter((item) => item.attemptId === event.attemptId && item.modelContextId === context.id)
          .flatMap((item) => item.resultRef ? [item.resultRef] : []),
        ...this.eventLog.filter((item) => item.eventType === 'attempt_completed' && item.attemptId === event.attemptId &&
          item.modelContextId === context.id).flatMap((item) => {
            const refs = record(item.payload).result_refs
            return Array.isArray(refs) ? refs.filter((ref): ref is string => typeof ref === 'string') : []
          }),
      ])
      if (view?.schema !== 'capstone-network-view/2.0' ||
          view.diagram.model.id !== context.modelId || view.diagram.model.revision !== context.modelRevision) return
      if (event.attemptId) {
        this.taskViews.set(event.attemptId, { attemptId: event.attemptId, eventSeq: event.eventSeq,
          pageId: page.pageId, context, view })
        if (this.taskViews.size > 64) this.taskViews.delete(this.taskViews.keys().next().value!)
      }
      setView(view)
      return
    }
    if (event.eventType === 'network_layer_unavailable') {
      if (event.attemptId) this.taskViews.delete(event.attemptId)
      this.networkDiagrams.delete(context.id)
      setView(null)
    }
  }
}
