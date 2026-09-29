import { type CommandReceipt, type EventPage, type ThreadSnapshot } from './threadProtocol'
import {
  CapstoneThreadClient, type ThreadCommand, type ThreadTransport, type ThreadTransportState,
} from './threadClient'

export type ThreadConnection = ThreadTransportState | 'connecting'

export type PendingThreadCommand = {
  command: ThreadCommand
  receipt?: CommandReceipt
}

export type ThreadProjectionState = {
  connection: ThreadConnection
  snapshot: ThreadSnapshot | null
  eventSeq: number
  resyncRequired: boolean
  pendingCommands: readonly PendingThreadCommand[]
  viewedGridPageId: string | null
}

type FixtureDocument = {
  snapshot: unknown
  events: unknown
  assertions?: { transport_state?: unknown }
}

function fixtureConnection(fixture: FixtureDocument): ThreadTransportState {
  const value = fixture.assertions?.transport_state
  if (value === 'reconnecting' || value === 'resync_required' || value === 'offline') return value
  return 'live'
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return value as Record<string, unknown>
}

/** A checked-fixture transport for the first Web/TUI projection prototype. */
export function createFixtureTransport(fixture: FixtureDocument): ThreadTransport {
  const receipts = new Map<string, Record<string, unknown>>()
  const snapshot = record(fixture.snapshot)
  const run = record(snapshot.run)
  const events = record(fixture.events)

  return {
    connectionState: fixtureConnection(fixture),
    getSnapshot: async () => fixture.snapshot,
    readEvents: async () => fixture.events,
    sendCommand: async (command) => {
      const existing = receipts.get(command.idempotency_key)
      if (existing) return existing
      const receipt = {
        schema: 'capstone-command-receipt/1',
        command_id: command.command_id,
        idempotency_key: command.idempotency_key,
        thread_id: command.thread_id,
        ...(typeof run.run_id === 'string' ? { run_id: run.run_id } : {}),
        status: 'accepted',
        ...(typeof events.next_event_seq === 'number' ? { accepted_event_seq: events.next_event_seq } : {}),
      }
      receipts.set(command.idempotency_key, receipt)
      return receipt
    },
  }
}

export class ThreadProjectionStore {
  private current: ThreadProjectionState = {
    connection: 'offline', snapshot: null, eventSeq: 0, resyncRequired: false,
    pendingCommands: [], viewedGridPageId: null,
  }

  private loadedThreadId: string | null = null

  constructor(private readonly client: CapstoneThreadClient) {}

  get state(): ThreadProjectionState {
    return this.current
  }

  async load(threadId: string): Promise<void> {
    const sameThread = this.loadedThreadId === threadId
    const previousView = this.loadedThreadId === threadId ? this.current.viewedGridPageId : null
    this.current = {
      ...this.current,
      connection: 'connecting', snapshot: null, eventSeq: 0, resyncRequired: false,
      pendingCommands: sameThread ? this.current.pendingCommands : [],
    }
    try {
      const snapshot = await this.client.load(threadId)
      const connection = this.client.connectionState
      this.current = {
        ...this.current,
        connection,
        snapshot,
        eventSeq: snapshot.lastEventSeq,
        resyncRequired: connection === 'resync_required',
        viewedGridPageId: previousView ?? snapshot.activeGridPageId,
      }
      this.loadedThreadId = threadId
    } catch (error) {
      this.current = { ...this.current, connection: 'resync_required', resyncRequired: true }
      throw error
    }
  }

  async catchUp(): Promise<EventPage> {
    if (this.current.resyncRequired || this.current.connection === 'resync_required') {
      throw new Error('thread is resync_required')
    }
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    try {
      const page = await this.client.readAfter(snapshot.threadId, this.current.eventSeq)
      if (page.threadId !== snapshot.threadId) throw new Error('event page thread does not match snapshot')
      this.current = { ...this.current, eventSeq: page.nextEventSeq }
      return page
    } catch (error) {
      this.current = { ...this.current, connection: 'resync_required', resyncRequired: true }
      throw error
    }
  }

  viewGridPage(pageId: string): void {
    if (!pageId) throw new Error('grid page id is required')
    this.current = { ...this.current, viewedGridPageId: pageId }
  }

  returnLiveGridPage(): void {
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    this.current = { ...this.current, viewedGridPageId: snapshot.activeGridPageId }
  }

  async dispatch(command: ThreadCommand): Promise<CommandReceipt> {
    const snapshot = this.current.snapshot
    if (!snapshot) throw new Error('thread snapshot is not loaded')
    if (this.current.resyncRequired || this.current.connection !== 'live') {
      throw new Error(`thread is ${this.current.connection}`)
    }
    if (command.thread_id !== snapshot.threadId) throw new Error('command thread does not match snapshot')
    const existing = this.current.pendingCommands.find((entry) => entry.command.idempotency_key === command.idempotency_key)
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
      return receipt
    } catch (error) {
      this.current = { ...this.current, connection: 'reconnecting' }
      throw error
    }
  }
}
