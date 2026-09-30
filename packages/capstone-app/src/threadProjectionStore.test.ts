import { describe, expect, it, vi } from 'vitest'
import { CapstoneThreadClient, type ThreadCommand, type ThreadTransport } from './threadClient'
import { createFixtureTransport, ThreadProjectionStore } from './threadProjectionStore'

const context = {
  id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: '7',
  implementation_family: 'pandapower', selection_revision: 'sel_2',
}

const idleFixture = {
  snapshot: {
    schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo_39',
    run: { run_id: 'run_001', state: 'open' }, active_model_context: context,
    active_grid_page_id: 'page_ieee39', current_attempt: null,
    last_event_seq: 0, base_event_seq: 0,
  },
  events: {
    schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
    after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
  },
  assertions: { transport_state: 'live' },
}

const historicalFixture = {
  snapshot: {
    schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo_39',
    run: { run_id: 'run_001', state: 'open' }, active_model_context: context,
    active_grid_page_id: 'page_ieee39', current_attempt: {
      turn_id: 'turn_004', attempt_id: 'attempt_004a', phase: 'running',
      target_model_context_id: 'ctx_ieee39_7',
    }, last_event_seq: 180, base_event_seq: 180,
  },
  events: {
    schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
    after_event_seq: 180, next_event_seq: 183, has_more: false,
    events: [
      {
        event_id: 'evt_181', event_seq: 181, event_type: 'grid_page_registered', event_version: 1,
        thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:01Z',
        visibility: 'public', payload: { grid_page_id: 'page_scigrid_2' },
      },
      {
        event_id: 'evt_182', event_seq: 182, event_type: 'grid_page_viewed', event_version: 1,
        thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:02Z',
        visibility: 'public', payload: { grid_page_id: 'page_scigrid_2', view_only: true },
      },
      {
        event_id: 'evt_183', event_seq: 183, event_type: 'attempt_progress', event_version: 1,
        thread_id: 'thr_demo_39', run_id: 'run_001', turn_id: 'turn_004', attempt_id: 'attempt_004a',
        model_context_id: 'ctx_ieee39_7', selection_revision: 'sel_2', occurred_at: '2026-09-30T00:00:03Z',
        visibility: 'public', payload: { phase: 'running' },
      },
    ],
  },
  assertions: { transport_state: 'live' },
}

function command(): ThreadCommand {
  return {
    schema: 'capstone-command/1', command_id: 'cmd_1', idempotency_key: 'idem_1',
    thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'cancel_live_attempt',
    expected_event_seq: 0, payload: { attempt_id: 'attempt_004a' },
  }
}

describe('ThreadProjectionStore', () => {
  it('loads a verified snapshot and initializes the live page', async () => {
    const transport = createFixtureTransport(idleFixture)
    const store = new ThreadProjectionStore(new CapstoneThreadClient(transport))

    await store.load('thr_demo_39')

    expect(store.state.connection).toBe('live')
    expect(store.state.eventSeq).toBe(0)
    expect(store.state.viewedGridPageId).toBe('page_ieee39')
    expect(store.state.resyncRequired).toBe(false)
  })

  it('catches up contiguously without changing the local historical page', async () => {
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(historicalFixture)))
    await store.load('thr_demo_39')
    store.viewGridPage('page_scigrid_2')

    await store.catchUp()

    expect(store.state.eventSeq).toBe(183)
    expect(store.state.viewedGridPageId).toBe('page_scigrid_2')
    expect(store.state.snapshot?.activeGridPageId).toBe('page_ieee39')
  })

  it('enters resync_required and does not advance on an event gap', async () => {
    const gapTransport: ThreadTransport = {
      getSnapshot: vi.fn().mockResolvedValue(idleFixture.snapshot),
      readEvents: vi.fn().mockResolvedValue({
        ...idleFixture.events,
        after_event_seq: 0,
        next_event_seq: 2,
        events: [{
          event_id: 'evt_2', event_seq: 2, event_type: 'command_accepted', event_version: 1,
          thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:01Z',
          visibility: 'public', payload: {},
        }],
      }),
      sendCommand: vi.fn(),
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(gapTransport))
    await store.load('thr_demo_39')

    await expect(store.catchUp()).rejects.toThrow('contiguous')
    expect(store.state.eventSeq).toBe(0)
    expect(store.state.connection).toBe('resync_required')
    expect(store.state.resyncRequired).toBe(true)
  })

  it('reconciles retries under one idempotency key', async () => {
    const transport = createFixtureTransport(idleFixture)
    const store = new ThreadProjectionStore(new CapstoneThreadClient(transport))
    await store.load('thr_demo_39')

    await store.dispatch(command())
    await store.dispatch(command())

    expect(store.state.pendingCommands).toHaveLength(1)
    expect(store.state.pendingCommands[0]).toMatchObject({
      command: { command_id: 'cmd_1', idempotency_key: 'idem_1' },
      receipt: { commandId: 'cmd_1', idempotencyKey: 'idem_1', status: 'accepted' },
    })
  })

  it('rejects a changed command that reuses an existing idempotency key', async () => {
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(idleFixture)))
    await store.load('thr_demo_39')
    await store.dispatch(command())

    await expect(store.dispatch({ ...command(), payload: { attempt_id: 'attempt_other' } }))
      .rejects.toThrow('idempotency key is already bound')
  })

  it('preserves the transport recovery gate from a fixture', async () => {
    const fixture = { ...idleFixture, assertions: { transport_state: 'resync_required' } }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))

    await store.load('thr_demo_39')

    expect(store.state.connection).toBe('resync_required')
    expect(store.state.resyncRequired).toBe(true)
    await expect(store.catchUp()).rejects.toThrow('resync_required')
  })

  it('projects streamed Attempt lifecycle events into the shared snapshot', async () => {
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'command_accepted', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', turnId: 'turn_1', attemptId: 'attempt_1',
          modelContextId: 'ctx_ieee39_7', selectionRevision: 'sel_2',
          occurredAt: '2026-09-30T00:00:01Z', visibility: 'public' as const, payload: {},
        }
        yield {
          eventId: 'evt_2', eventSeq: 2, eventType: 'attempt_started', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', turnId: 'turn_1', attemptId: 'attempt_1',
          modelContextId: 'ctx_ieee39_7', selectionRevision: 'sel_2',
          occurredAt: '2026-09-30T00:00:02Z', visibility: 'public' as const, payload: {},
        }
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    await store.load('thr_demo_39')

    await store.consumeEvents()

    expect(store.state.eventSeq).toBe(2)
    expect(store.state.snapshot?.currentAttempt).toMatchObject({ attemptId: 'attempt_1', phase: 'running' })
  })

  it('projects a model context switch and clears its staged state', async () => {
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'command_accepted', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', occurredAt: '2026-09-30T00:00:01Z',
          visibility: 'public' as const, payload: { kind: 'switch_model' },
        }
        yield {
          eventId: 'evt_2', eventSeq: 2, eventType: 'model_context_change_pending', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_ieee39_7', selectionRevision: 'sel_2',
          occurredAt: '2026-09-30T00:00:02Z', visibility: 'public' as const,
          payload: {
            command_id: 'cmd_switch', model_id: 'pypsa39', model_revision: 'revision:sha256:bbbb',
            implementation_family: 'pypsa', selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] },
          },
        }
        yield {
          eventId: 'evt_3', eventSeq: 3, eventType: 'model_context_activated', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_pypsa39_1', selectionRevision: 'sel_0',
          occurredAt: '2026-09-30T00:00:03Z', visibility: 'public' as const,
          payload: {
            model_context: {
              id: 'ctx_pypsa39_1', model_id: 'pypsa39', model_revision: 'revision:sha256:bbbb',
              implementation_family: 'pypsa', selection_revision: 'sel_0',
            }, active_grid_page_id: 'page_pypsa39',
          },
        }
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    await store.load('thr_demo_39')
    await store.consumeEvents()

    expect(store.state.snapshot?.activeModelContext.modelId).toBe('pypsa39')
    expect(store.state.snapshot?.activeGridPageId).toBe('page_pypsa39')
    expect(store.state.viewedGridPageId).toBe('page_pypsa39')
    expect(store.state.snapshot?.pendingModelSwitch).toBeUndefined()
  })
})
