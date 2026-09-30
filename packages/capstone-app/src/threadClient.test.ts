import { describe, expect, it, vi } from 'vitest'
import { buildThreadCommand, CapstoneThreadClient, type ThreadCommand, type ThreadTransport } from './threadClient'

const snapshot = {
  schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo_39',
  run: { run_id: 'run_001', state: 'open' },
  active_model_context: {
    id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: '7',
    implementation_family: 'pandapower', selection_revision: 'sel_2',
  },
  active_grid_page_id: 'page_ieee39', current_attempt: null,
  last_event_seq: 0, base_event_seq: 0,
}

const events = {
  schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
  after_event_seq: 0, next_event_seq: 1, has_more: false,
  events: [{
    event_id: 'evt_1', event_seq: 1, event_type: 'command_accepted', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:00Z',
    visibility: 'public', payload: {},
  }],
}

const receipt = {
  schema: 'capstone-command-receipt/1', command_id: 'cmd_1', idempotency_key: 'idem_1',
  thread_id: 'thr_demo_39', run_id: 'run_001', status: 'accepted', accepted_event_seq: 1,
}

function command(): ThreadCommand {
  return {
    schema: 'capstone-command/1', command_id: 'cmd_1', idempotency_key: 'idem_1',
    thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'cancel_live_attempt',
    expected_event_seq: 0, payload: { attempt_id: 'attempt_004a' },
  }
}

describe('CapstoneThreadClient', () => {
  it('builds a model switch command with the verified cursor and caller identity', () => {
    expect(buildThreadCommand({
      threadId: 'thr_demo_39', runId: 'run_001', kind: 'switch_model',
      expectedEventSeq: 7, commandId: 'cmd_switch_001', idempotencyKey: 'idem_switch_001',
      payload: { model_id: 'pypsa39' },
    })).toEqual({
      schema: 'capstone-command/1', command_id: 'cmd_switch_001', idempotency_key: 'idem_switch_001',
      thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'switch_model', expected_event_seq: 7,
      payload: { model_id: 'pypsa39' },
    })
  })

  it('creates a Thread and validates its pinned snapshot', async () => {
    const transport: ThreadTransport = {
      createThread: vi.fn().mockResolvedValue(snapshot),
      getSnapshot: vi.fn(), readEvents: vi.fn(), sendCommand: vi.fn(),
    }

    const result = await new CapstoneThreadClient(transport).create()

    expect(result.activeModelContext.modelId).toBe('ieee39')
    expect(transport.createThread).toHaveBeenCalledWith(undefined, undefined)
  })

  it('validates and returns a typed snapshot from the transport', async () => {
    const transport: ThreadTransport = {
      getSnapshot: vi.fn().mockResolvedValue(snapshot),
      readEvents: vi.fn().mockResolvedValue(events),
      sendCommand: vi.fn().mockResolvedValue(receipt),
    }

    const result = await new CapstoneThreadClient(transport).load('thr_demo_39')

    expect(result.activeGridPageId).toBe('page_ieee39')
    expect(transport.getSnapshot).toHaveBeenCalledWith('thr_demo_39', undefined)
  })

  it('forwards the cursor and validates a contiguous event page', async () => {
    const transport: ThreadTransport = {
      getSnapshot: vi.fn(), readEvents: vi.fn().mockResolvedValue(events), sendCommand: vi.fn(),
    }

    const result = await new CapstoneThreadClient(transport).readAfter('thr_demo_39', 0)

    expect(result.nextEventSeq).toBe(1)
    expect(transport.readEvents).toHaveBeenCalledWith('thr_demo_39', 0, undefined)
  })

  it('passes the same command identity and returns the typed receipt', async () => {
    const transport: ThreadTransport = {
      getSnapshot: vi.fn(), readEvents: vi.fn(), sendCommand: vi.fn().mockResolvedValue(receipt),
    }
    const value = command()

    await expect(new CapstoneThreadClient(transport).send(value)).resolves.toMatchObject({
      commandId: 'cmd_1', idempotencyKey: 'idem_1', status: 'accepted',
    })
    expect(transport.sendCommand).toHaveBeenCalledWith(value, undefined)
  })

  it('submits a model switch through the same typed command transport', async () => {
    const transport: ThreadTransport = {
      getSnapshot: vi.fn(), readEvents: vi.fn(), sendCommand: vi.fn().mockResolvedValue(receipt),
    }

    await new CapstoneThreadClient(transport).switchModel(
      'thr_demo_39', 'run_001', 'pypsa39', 7,
      { commandId: 'cmd_switch_001', idempotencyKey: 'idem_switch_001' },
    )

    expect(transport.sendCommand).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'switch_model', expected_event_seq: 7, payload: { model_id: 'pypsa39' },
    }), undefined)
  })

  it('does not turn an invalid receipt into an accepted command', async () => {
    const transport: ThreadTransport = {
      getSnapshot: vi.fn(), readEvents: vi.fn(), sendCommand: vi.fn().mockResolvedValue({ status: 'accepted' }),
    }

    await expect(new CapstoneThreadClient(transport).send(command())).rejects.toThrow('missing field')
  })

  it('exposes the transport SSE stream as typed events', async () => {
    const transport: ThreadTransport = {
      getSnapshot: vi.fn(), readEvents: vi.fn(), sendCommand: vi.fn(),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'command_accepted', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', occurredAt: '2026-09-30T00:00:00Z',
          visibility: 'public', payload: {},
        }
      },
    }
    const values = []
    for await (const event of new CapstoneThreadClient(transport).events('thr_demo_39', 0)) {
      values.push(event)
    }
    expect(values[0]?.eventSeq).toBe(1)
  })
})
