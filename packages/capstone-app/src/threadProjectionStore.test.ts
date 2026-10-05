import { describe, expect, it, vi } from 'vitest'
import { CapstoneThreadClient, type ThreadCommand, type ThreadTransport } from './threadClient'
import { createFixtureTransport, instructionOrdinal, ThreadProjectionStore } from './threadProjectionStore'
import { sampleDiagramView } from './networkFixture'
import { historyContexts, historyFixture } from './threadHistory.test-support'
import { parseEventEnvelope } from './threadProtocol'

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
  catalog: {
    schema: 'capstone-thread-catalog/1', models: [], profiles: [],
  },
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

const dynamicDiagram = {
  ...sampleDiagramView.diagram,
  model: { id: 'ieee39', revision: '7', source: 'pypsamodelctl' },
}
const dynamicLayer = {
  ...sampleDiagramView.layer,
  model_revision: '7',
}

function command(): ThreadCommand {
  return {
    schema: 'capstone-command/1', command_id: 'cmd_1', idempotency_key: 'idem_1',
    thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'cancel_live_attempt',
    expected_event_seq: 0, payload: { attempt_id: 'attempt_004a' },
  }
}

describe('ThreadProjectionStore', () => {
  it('numbers instructions without counting cancellations and preserves retry numbering', () => {
    const events = [
      ['send_auto', 'attempt_a', 'turn_a', {}],
      ['cancel_live_attempt', 'attempt_a', 'turn_a', {}],
      ['send_professional', 'attempt_b', 'turn_b', {}],
      ['retry_new_attempt', 'attempt_retry', 'turn_b', { retry_of: 'attempt_b' }],
    ].map(([kind, attempt_id, turn_id, payload], index) => parseEventEnvelope({
      event_id: `evt_number_${index}`, event_seq: index + 1, event_type: 'command_accepted', event_version: 1,
      thread_id: 'thr_demo_39', run_id: 'run_001', attempt_id, turn_id,
      occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload: { kind, payload },
    }))
    expect(instructionOrdinal(events, 'attempt_a')).toBe(1)
    expect(instructionOrdinal(events, 'attempt_b')).toBe(2)
    expect(instructionOrdinal(events, 'attempt_retry')).toBe(2)
  })
  it('retains each instruction layer separately and restores it from history', async () => {
    const diagram = { ...dynamicDiagram, coordinate_system: 'schematic' }
    const rawEvents = [
      ['network_diagram', 'attempt_flow', { diagram }],
      ['network_layer', 'attempt_flow', { ordinal: 1, layer: { ...dynamicLayer, focus_ids: ['line:1'], overlay: { metric: 'loading_percent', unit: '%', source_ref: `result:sha256:${'c'.repeat(64)}`, values: [{ id: 'line:1', value: 42 }] } } }],
      ['attempt_completed', 'attempt_flow', { result_refs: [`result:sha256:${'c'.repeat(64)}`] }],
      ['network_diagram', 'attempt_rank', { diagram }],
      ['network_layer', 'attempt_rank', { ordinal: 1, layer: { ...dynamicLayer, focus_ids: ['line:1'], overlay: null } }],
    ].map(([event_type, attempt_id, payload], index) => ({ event_id: `evt_task_${index}`, event_seq: index + 1,
      event_type, attempt_id, payload, event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001',
      model_context_id: context.id, occurred_at: '2026-10-05T00:00:00Z', visibility: 'public' }))
    const fixture = { ...structuredClone(idleFixture), snapshot: { ...idleFixture.snapshot, last_event_seq: rawEvents.length },
      events: { ...idleFixture.events, next_event_seq: rawEvents.length, events: rawEvents } }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))
    await store.load('thr_demo_39')
    expect(store.networkTasks.map((task) => task.attemptId)).toEqual(['attempt_flow', 'attempt_rank'])
    expect(store.networkTasks[0].view.layer.overlay).not.toBeNull()
    expect(store.networkTasks[1].view.layer.overlay).toBeNull()
    expect(store.state.networkView).toEqual(store.networkTasks[1].view)
    await store.load('thr_demo_39')
    expect(store.networkTasks.map((task) => task.attemptId)).toEqual(['attempt_flow', 'attempt_rank'])
  })

  it.each(['event', 'failure'])('ignores a superseded stream %s after a newer load', async (outcome) => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => { release = resolve })
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...createFixtureTransport(structuredClone(idleFixture)),
      streamEvents: async function* () {
        await gate
        if (outcome === 'failure') throw new Error('old stream failed')
        yield parseEventEnvelope({ event_id: 'evt_old', event_seq: 1, event_type: 'assistant_text_delta',
          event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z',
          visibility: 'public', payload: { text: 'superseded' } })
      },
    }))
    await store.load('thr_demo_39')
    const oldStream = store.consumeEvents()
    await store.load('thr_demo_39')
    release()
    await oldStream
    expect(store.state.connection).toBe('live')
    expect(store.state.eventSeq).toBe(0)
    expect(store.publicEvents).toEqual([])
  })

  it('ignores an old catch-up failure after a newer load', async () => {
    const transport = createFixtureTransport(structuredClone(idleFixture))
    let reject!: (error: Error) => void
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...transport,
      readEvents: async () => new Promise((_resolve, fail) => { reject = fail }),
    }))
    await store.load('thr_demo_39')
    const oldRead = store.catchUp()
    await store.load('thr_demo_39')
    reject(new Error('old event request failed'))
    await oldRead.catch(() => {})
    expect(store.state.connection).toBe('live')
  })

  it('does not let an older load erase events admitted after the latest load', async () => {
    const transport = createFixtureTransport(structuredClone(idleFixture))
    let release!: (snapshot: unknown) => void
    let calls = 0
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...transport,
      getSnapshot: async () => ++calls === 1 ? new Promise((resolve) => { release = resolve }) : idleFixture.snapshot,
    }))
    const oldLoad = store.load('thr_demo_39')
    await store.load('thr_demo_39')
    await store.dispatch({ ...command(), kind: 'send_auto', payload: { text: '有哪些 PyPSA 的电网模型？' } })
    const admittedCursor = store.state.eventSeq
    const admittedEvents = [...store.publicEvents]
    expect(admittedCursor).toBeGreaterThan(0)
    release(idleFixture.snapshot)
    await oldLoad
    expect(store.state.eventSeq).toBe(admittedCursor)
    expect(store.publicEvents).toEqual(admittedEvents)
  })

  it('ignores a failed superseded load after the latest projection becomes live', async () => {
    const transport = createFixtureTransport(structuredClone(idleFixture))
    let reject!: (error: Error) => void
    let calls = 0
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...transport,
      getSnapshot: async () => ++calls === 1 ? new Promise((_resolve, fail) => { reject = fail }) : idleFixture.snapshot,
    }))
    const oldLoad = store.load('thr_demo_39')
    await store.load('thr_demo_39')
    reject(new Error('old request failed'))
    await oldLoad
    expect(store.state.connection).toBe('live')
    expect(store.state.snapshot?.threadId).toBe('thr_demo_39')
  })

  it('does not duplicate events or regress the cursor when catch-up overlaps SSE delivery', async () => {
    const events = [1, 2].map((sequence) => parseEventEnvelope({ event_id: `evt_${sequence}`, event_seq: sequence, event_type: 'assistant_text_delta', event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload: { text: `${sequence}` } }))
    let finishRead: ((value: unknown) => void) | undefined
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...createFixtureTransport(idleFixture),
      readEvents: async () => new Promise((resolve) => { finishRead = resolve }),
      streamEvents: async function* () { yield* events },
    }))
    await store.load('thr_demo_39')
    const read = store.catchUp()
    await store.consumeEvents()
    finishRead!({ schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 0, next_event_seq: 1, has_more: false, events: [{ event_id: 'evt_1', event_seq: 1, event_type: 'assistant_text_delta', event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload: { text: '1' } }] })
    await expect(read).resolves.toBeTruthy()
    expect(store.state.eventSeq).toBe(2)
    expect(store.publicEvents).toHaveLength(2)
  })
  it.each(['model_context_activated', 'model_context_reopened'])('restores the exact previous live diagram after failed %s and on reload', async (changeType) => {
    const nextContext = { ...context, id: 'ctx_next', ...(changeType === 'model_context_activated' ? { model_id: 'pypsa39', implementation_family: 'pypsa' } : {}) }
    const events = [
      ['network_diagram', context.id, { diagram: dynamicDiagram }],
      ['network_layer', context.id, { ordinal: 1, layer: dynamicLayer }],
      [changeType, nextContext.id, { model_context: nextContext, previous_context: context, active_grid_page_id: changeType === 'model_context_activated' ? 'page_pypsa39' : 'page_ieee39', previous_grid_page_id: 'page_ieee39' }],
      ['model_context_reverted', context.id, { restored_context: context, restored_grid_page_id: 'page_ieee39' }],
    ].map(([event_type, model_context_id, payload], index) => ({
      event_id: `evt_${index + 1}`, event_seq: index + 1, event_type, event_version: 1, model_context_id,
      thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload,
    }))
    const transport = { ...createFixtureTransport(idleFixture),
      streamEvents: async function* () { for (const event of events) yield parseEventEnvelope(event) },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(transport))
    await store.load('thr_demo_39')
    await store.consumeEvents()
    expect(store.state.snapshot?.activeModelContext.id).toBe(context.id)
    expect(store.state.networkView?.diagram.model.id).toBe('ieee39')
    const restored = store.state.networkView
    const replay = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport({ ...idleFixture,
      snapshot: { ...idleFixture.snapshot, last_event_seq: events.length },
      events: { ...idleFixture.events, next_event_seq: events.length, events },
    })))
    await replay.load('thr_demo_39')
    expect(replay.state.networkView).toEqual(restored)
  })
  it('restores model pages and their own context-bound network views from typed history', async () => {
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(historyFixture())))
    await store.load('thr_history')

    expect(store.state.gridPages.map((page) => page.pageId)).toEqual(['page_ieee39', 'page_regional-six-bus'])
    const historical = store.state.gridPages.find((page) => page.pageId === 'page_regional-six-bus')!
    expect(historical.context.id).toBe(historyContexts.historical.id)
    expect(historical.networkView?.diagram.model).toMatchObject({ id: 'regional-six-bus', revision: historyContexts.historical.model_revision })
    expect(store.state.networkView?.diagram.model).toMatchObject({ id: 'ieee39', revision: historyContexts.active.model_revision })
    const before = store.state.snapshot?.toDocument()
    store.viewGridPage(historical.pageId)
    expect(store.state.snapshot?.toDocument()).toEqual(before)
    expect(store.state.pendingCommands).toEqual([])
    await store.load('thr_history')
    expect(store.state.viewedGridPageId).toBe(historical.pageId)
    expect(store.state.gridPages.find((page) => page.pageId === historical.pageId)?.networkView).toEqual(historical.networkView)
  })

  it('leaves a historical page unavailable when only another context has a diagram', async () => {
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(historyFixture(false))))
    await store.load('thr_history')

    expect(store.state.gridPages.find((page) => page.pageId === 'page_regional-six-bus')?.networkView).toBeNull()
    expect(store.state.networkView?.diagram.model.id).toBe('ieee39')
  })

  it('does not reuse an earlier diagram when a historical model was reopened at the same revision', async () => {
    const fixture = historyFixture()
    const document = fixture.events as { events: Record<string, unknown>[]; next_event_seq: number }
    const nextContext = { ...historyContexts.historical, id: 'ctx_regional_reopened' }
    const switchIndex = document.events.findIndex((event) =>
      event.event_type === 'model_context_activated' && event.model_context_id === historyContexts.active.id)
    const switchEvent = document.events[switchIndex]
    const switchPayload = switchEvent.payload as Record<string, unknown>
    switchPayload.previous_context = nextContext
    document.events.splice(switchIndex, 0, {
      ...switchEvent, event_type: 'model_context_reopened', model_context_id: nextContext.id,
      payload: { model_context: nextContext, previous_context: historyContexts.historical,
        active_grid_page_id: 'page_regional-six-bus', previous_grid_page_id: 'page_regional-six-bus', reason: 'explicit_reopen' },
    })
    document.events.forEach((event, index) => Object.assign(event, { event_seq: index + 1, event_id: `evt_${index + 1}` }))
    document.next_event_seq = document.events.length
    const snapshotDocument = fixture.snapshot as Record<string, unknown>
    snapshotDocument.last_event_seq = document.events.length
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))
    await store.load('thr_history')

    expect(store.state.gridPages).toHaveLength(2)
    const historical = store.state.gridPages.find((page) => page.pageId === 'page_regional-six-bus')!
    expect(historical.context.id).toBe(nextContext.id)
    expect(historical.networkView).toBeNull()
    expect(store.state.networkView?.diagram.model.id).toBe('ieee39')
  })

  it('adds newly activated pages during live catch-up without moving a selected historical page', async () => {
    const fixture = historyFixture()
    const cursor = (fixture.snapshot as { last_event_seq: number }).last_event_seq
    const nextContext = { ...historyContexts.historical, id: 'ctx_pypsa39', model_id: 'pypsa39' }
    const store = new ThreadProjectionStore(new CapstoneThreadClient({
      ...createFixtureTransport(fixture),
      streamEvents: async function* () {
        yield parseEventEnvelope({
          event_id: `evt_${cursor + 1}`, event_seq: cursor + 1, event_type: 'model_context_activated', event_version: 1,
          thread_id: 'thr_history', run_id: 'run_history', model_context_id: nextContext.id,
          occurred_at: '2026-10-05T00:00:01Z', visibility: 'public',
          payload: { model_context: nextContext, previous_context: historyContexts.active,
            active_grid_page_id: 'page_pypsa39', previous_grid_page_id: 'page_ieee39' },
        })
      },
    }))
    await store.load('thr_history')
    store.viewGridPage('page_regional-six-bus')
    const historical = store.state.gridPages.find((page) => page.pageId === 'page_regional-six-bus')
    await store.consumeEvents()

    expect(store.state.viewedGridPageId).toBe('page_regional-six-bus')
    expect(store.state.snapshot?.activeModelContext.id).toBe(nextContext.id)
    expect(store.state.gridPages.map((page) => page.pageId)).toEqual(['page_ieee39', 'page_regional-six-bus', 'page_pypsa39'])
    expect(store.state.gridPages.find((page) => page.pageId === 'page_regional-six-bus')).toEqual(historical)
    expect(store.state.networkView).toBeNull()
  })

  it('loads a verified snapshot and initializes the live page', async () => {
    const transport = createFixtureTransport(idleFixture)
    const store = new ThreadProjectionStore(new CapstoneThreadClient(transport))

    await store.load('thr_demo_39')

    expect(store.state.connection).toBe('live')
    expect(store.state.eventSeq).toBe(0)
    expect(store.state.viewedGridPageId).toBe('page_ieee39')
    expect(store.state.resyncRequired).toBe(false)
    expect(store.state.catalog).toEqual({ models: [], profiles: [] })
  })

  it('restores public history from the snapshot cursor when a Thread is reloaded', async () => {
    const fixture = {
      ...idleFixture,
      snapshot: { ...idleFixture.snapshot, last_event_seq: 1 },
      events: {
        ...idleFixture.events,
        next_event_seq: 1,
        events: [{
          event_id: 'evt_1', event_seq: 1, event_type: 'assistant_text_delta', event_version: 1,
          thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:01Z',
          visibility: 'public', payload: { text: '历史回答' },
        }],
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))

    await store.load('thr_demo_39')
    expect(store.publicEvents.map((event) => event.eventSeq)).toEqual([1])
    await store.load('thr_demo_39')

    expect(store.publicEvents.map((event) => event.payload.text)).toEqual(['历史回答'])
  })

  it('restores the captured cursor when the history page also contains a later event', async () => {
    const laterEventTransport: ThreadTransport = {
      getSnapshot: vi.fn().mockResolvedValue({ ...idleFixture.snapshot, last_event_seq: 1 }),
      readEvents: vi.fn().mockResolvedValue({
        ...idleFixture.events,
        next_event_seq: 2,
        events: [
          {
            event_id: 'evt_1', event_seq: 1, event_type: 'assistant_text_delta', event_version: 1,
            thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:01Z',
            visibility: 'public', payload: { text: '已捕获' },
          },
          {
            event_id: 'evt_2', event_seq: 2, event_type: 'assistant_text_delta', event_version: 1,
            thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:02Z',
            visibility: 'public', payload: { text: '快照之后追加' },
          },
        ],
      }),
      sendCommand: vi.fn(),
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(laterEventTransport))

    await expect(store.load('thr_demo_39')).resolves.toBeUndefined()
    expect(store.state.eventSeq).toBe(1)
    expect(store.publicEvents.map((event) => event.payload.text)).toEqual(['已捕获'])
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

  it('adopts admitted result projections from a completed Attempt event', async () => {
    const projection = {
      schema: 'capstone-result-projection/1.0', result_id: 'result_projection_1',
      result_ref: `result:sha256:${'a'.repeat(64)}`, evidence_refs: [`evidence:sha256:${'b'.repeat(64)}`],
      thread_id: 'thr_demo_39', run_id: 'run_001', turn_id: 'turn_1', attempt_id: 'attempt_1',
      model_context_id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`,
      source: { capability_id: 'analysis.powerflow.ac.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
      status: 'completed', summary: [], tables: [], element_refs: [], overlay: null,
    }
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'attempt_completed', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', turnId: 'turn_1', attemptId: 'attempt_1',
          modelContextId: 'ctx_ieee39_7', selectionRevision: 'sel_2',
          occurredAt: '2026-09-30T00:00:01Z', visibility: 'public' as const,
          payload: { result_projections: [projection] },
        }
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    await store.load('thr_demo_39')
    await store.consumeEvents()

    expect(store.state.snapshot?.resultProjections?.map((item) => item.resultId)).toEqual(['result_projection_1'])
  })

  it('replays a matching diagram and layer into the current model view', async () => {
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'network_diagram', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', turnId: 'turn_1', attemptId: 'attempt_1',
          modelContextId: 'ctx_ieee39_7', selectionRevision: 'sel_2',
          occurredAt: '2026-09-30T00:00:01Z', visibility: 'public' as const,
          payload: { diagram: dynamicDiagram },
        }
        yield {
          eventId: 'evt_2', eventSeq: 2, eventType: 'network_layer', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', turnId: 'turn_1', attemptId: 'attempt_1',
          modelContextId: 'ctx_ieee39_7', selectionRevision: 'sel_2',
          occurredAt: '2026-09-30T00:00:02Z', visibility: 'public' as const,
          payload: { ordinal: 1, layer: dynamicLayer },
        }
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    await store.load('thr_demo_39')
    await store.consumeEvents()

    expect(store.state.networkView?.diagram.model.revision).toBe('7')
    expect(store.state.networkView?.layer.diagram_ref).toBe(store.state.networkView?.diagram.ref)
  })

  it('does not reuse a prior context diagram after a model switch', async () => {
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'network_diagram', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_ieee39_7',
          occurredAt: '2026-09-30T00:00:01Z', visibility: 'public' as const,
          payload: { diagram: dynamicDiagram },
        }
        yield {
          eventId: 'evt_2', eventSeq: 2, eventType: 'network_layer', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_ieee39_7',
          occurredAt: '2026-09-30T00:00:02Z', visibility: 'public' as const,
          payload: { ordinal: 1, layer: dynamicLayer },
        }
        yield {
          eventId: 'evt_3', eventSeq: 3, eventType: 'model_context_reopened', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_pypsa_1',
          selectionRevision: 'sel_0', occurredAt: '2026-09-30T00:00:03Z', visibility: 'public' as const,
          payload: {
            model_context: {
              id: 'ctx_pypsa_1', model_id: 'regional-six-bus', model_revision: 'revision:sha256:bbbb',
              implementation_family: 'pypsa', selection_revision: 'sel_0',
            }, active_grid_page_id: 'page_regional_six_bus', reason: 'explicit_reopen',
          },
        }
        yield {
          eventId: 'evt_4', eventSeq: 4, eventType: 'network_diagram', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_ieee39_7',
          occurredAt: '2026-09-30T00:00:04Z', visibility: 'public' as const,
          payload: { diagram: dynamicDiagram },
        }
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    await store.load('thr_demo_39')
    await store.consumeEvents()

    expect(store.state.snapshot?.activeModelContext.modelId).toBe('regional-six-bus')
    expect(store.state.networkView).toBeNull()
  })

  it('records public events and notifies the workspace projection subscriber', async () => {
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        yield {
          eventId: 'evt_1', eventSeq: 1, eventType: 'assistant_text_delta', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', occurredAt: '2026-09-30T00:00:01Z',
          visibility: 'public' as const, payload: { text: 'ready' },
        }
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    let updates = 0
    store.subscribe(() => { updates += 1 })
    await store.load('thr_demo_39')
    await store.consumeEvents()

    expect(store.publicEvents.map((event) => event.eventSeq)).toEqual([1])
    expect(updates).toBeGreaterThanOrEqual(2)
  })

  it('keeps a transient stream failure reconnectable instead of requiring resync', async () => {
    const streamTransport: ThreadTransport = {
      ...createFixtureTransport(idleFixture),
      streamEvents: async function* () {
        throw new Error('socket closed')
      },
    }
    const store = new ThreadProjectionStore(new CapstoneThreadClient(streamTransport))
    await store.load('thr_demo_39')

    await expect(store.consumeEvents()).rejects.toThrow('socket closed')
    expect(store.state.connection).toBe('reconnecting')
    expect(store.state.resyncRequired).toBe(false)
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
            implementation_family: 'pypsa', reason: 'explicit_reopen',
            selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] },
          },
        }
        yield {
          eventId: 'evt_3', eventSeq: 3, eventType: 'model_context_reopened', eventVersion: 1,
          threadId: 'thr_demo_39', runId: 'run_001', modelContextId: 'ctx_pypsa39_1', selectionRevision: 'sel_0',
          occurredAt: '2026-09-30T00:00:03Z', visibility: 'public' as const,
          payload: {
            model_context: {
              id: 'ctx_pypsa39_1', model_id: 'pypsa39', model_revision: 'revision:sha256:bbbb',
              implementation_family: 'pypsa', selection_revision: 'sel_0',
            }, active_grid_page_id: 'page_pypsa39',
            reason: 'explicit_reopen',
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
    expect(store.publicEvents.find((event) => event.eventType === 'model_context_reopened')?.payload.reason)
      .toBe('explicit_reopen')
  })
})
