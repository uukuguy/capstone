import {
  parseCommandReceipt, parseEventPage, parseThreadSnapshot,
  type CommandReceipt, type EventEnvelope, type EventPage, type ThreadSnapshot,
} from './threadProtocol'

export type ThreadCommand = {
  schema: 'capstone-command/1'
  command_id: string
  idempotency_key: string
  thread_id: string
  run_id?: string
  kind: string
  expected_event_seq: number
  payload: Record<string, unknown>
}

export type ThreadTransportState = 'live' | 'reconnecting' | 'resync_required' | 'offline'

export interface ThreadTransport {
  createThread?(modelId?: string, signal?: AbortSignal): Promise<unknown>
  getSnapshot(threadId: string, signal?: AbortSignal): Promise<unknown>
  readEvents(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<unknown>
  sendCommand(command: ThreadCommand, signal?: AbortSignal): Promise<unknown>
  streamEvents?(threadId: string, afterEventSeq: number, signal?: AbortSignal): AsyncGenerator<EventEnvelope>
  readonly connectionState?: ThreadTransportState
}

const commandIdentifierPattern = /^[a-z][a-z0-9_-]{0,63}$/

export function buildThreadCommand(input: {
  threadId: string
  runId?: string
  kind: string
  expectedEventSeq: number
  commandId: string
  idempotencyKey: string
  payload: Record<string, unknown>
}): ThreadCommand {
  for (const [name, value] of [
    ['threadId', input.threadId], ['commandId', input.commandId], ['idempotencyKey', input.idempotencyKey], ['kind', input.kind],
  ] as const) {
    if (!commandIdentifierPattern.test(value)) throw new Error(`${name} is invalid`)
  }
  if (input.runId !== undefined && !commandIdentifierPattern.test(input.runId)) throw new Error('runId is invalid')
  if (!Number.isSafeInteger(input.expectedEventSeq) || input.expectedEventSeq < 0) throw new Error('expectedEventSeq is invalid')
  return {
    schema: 'capstone-command/1', command_id: input.commandId,
    idempotency_key: input.idempotencyKey, thread_id: input.threadId,
    ...(input.runId === undefined ? {} : { run_id: input.runId }),
    kind: input.kind, expected_event_seq: input.expectedEventSeq,
    payload: { ...input.payload },
  }
}

export class CapstoneThreadClient {
  constructor(private readonly transport: ThreadTransport) {}

  get connectionState(): ThreadTransportState {
    return this.transport.connectionState ?? 'live'
  }

  async create(modelId?: string, signal?: AbortSignal): Promise<ThreadSnapshot> {
    if (!this.transport.createThread) throw new Error('Thread transport does not support creation')
    return parseThreadSnapshot(await this.transport.createThread(modelId, signal))
  }

  async load(threadId: string, signal?: AbortSignal): Promise<ThreadSnapshot> {
    return parseThreadSnapshot(await this.transport.getSnapshot(threadId, signal))
  }

  async readAfter(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<EventPage> {
    return parseEventPage(
      await this.transport.readEvents(threadId, afterEventSeq, signal),
      afterEventSeq,
    )
  }

  async send(command: ThreadCommand, signal?: AbortSignal): Promise<CommandReceipt> {
    return parseCommandReceipt(await this.transport.sendCommand(command, signal))
  }

  async switchModel(
    threadId: string, runId: string, modelId: string, expectedEventSeq: number,
    identity: { commandId: string; idempotencyKey: string }, signal?: AbortSignal,
  ): Promise<CommandReceipt> {
    return this.send(buildThreadCommand({
      threadId, runId, kind: 'switch_model', expectedEventSeq,
      commandId: identity.commandId, idempotencyKey: identity.idempotencyKey,
      payload: { model_id: modelId },
    }), signal)
  }

  async *events(threadId: string, afterEventSeq: number, signal?: AbortSignal): AsyncGenerator<EventEnvelope> {
    if (!this.transport.streamEvents) throw new Error('Thread transport does not support SSE')
    for await (const event of this.transport.streamEvents(threadId, afterEventSeq, signal)) yield event
  }
}
