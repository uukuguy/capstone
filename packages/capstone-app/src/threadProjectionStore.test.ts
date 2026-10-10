import { describe, expect, it, vi } from 'vitest'
import { CapstoneThreadClient, type ThreadCommand, type ThreadTransport } from './threadClient'
import { createFixtureTransport, instructionOrdinal, ThreadProjectionStore } from './threadProjectionStore'
import { sampleDiagramView } from './networkFixture'
import { historyContexts, historyFixture, historyWorkspace } from './threadHistory.test-support'
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

it('loads durable model membership independently of the legacy snapshot', async () => {
  const model = { entry_id: 'mdl_ieee39', model_id: context.model_id, model_revision: context.model_revision,
    implementation_family: context.implementation_family, authority_model_ref: 'gridctl:ieee39', display_name: 'IEEE-39', diagram_provider_id: 'gridctl', last_active_seq: 0 }
  const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...createFixtureTransport(idleFixture),
    getModels: async () => ({ schema: 'capstone-thread-model-workspace/1', thread_id: 'thr_demo_39', run_id: 'run_001', event_seq: 0,
      current_entry_id: model.entry_id, models: [model], blocked_reason: null }) }))
  await store.load('thr_demo_39')
  expect(store.state.modelWorkspace?.currentEntryId).toBe(model.entry_id)
})

it('keeps model working pages distinct from historical Context views', async () => {
  const fixture = historyFixture()
  const workspace = historyWorkspace((fixture.snapshot as { last_event_seq: number }).last_event_seq)
  const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...createFixtureTransport(fixture), getModels: async () => workspace }))
  await store.load('thr_history')
  expect(store.state.gridPages).toHaveLength(3)
  expect(store.modelWorkingPages).toHaveLength(2)
  expect(store.modelWorkingPages.find(page => page.entryId === 'mdl_ieee')?.context?.id).toBe(historyContexts.active.id)
  workspace.models = workspace.models.slice(0, 1)
  await store.refreshModels()
  expect(store.modelWorkingPages).toHaveLength(1)
  expect(store.state.gridPages.find(page => page.context.id === historyContexts.historical.id)).toBeTruthy()
})

it('does not label a fresh baseline with an older analysis instruction', async () => {
  const fixture = historyFixture()
  const document = fixture.events as { events: Record<string, unknown>[]; next_event_seq: number }
  const source = [...document.events].reverse().find(event => event.event_type === 'network_diagram')!
  const baseline = { ...source, event_id: 'evt_baseline', event_seq: document.events.length + 1, attempt_id: undefined }
  document.events.push(baseline)
  document.next_event_seq = baseline.event_seq
  ;(fixture.snapshot as { last_event_seq: number }).last_event_seq = baseline.event_seq
  const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))
  await store.load('thr_history')
  expect(store.state.networkView).toBeTruthy()
  expect(store.latestNetworkEvent).toBeUndefined()
})

it('loads only the latest history page and prepends older events without moving the live cursor', async () => {
  const events = Array.from({ length: 10 }, (_, index) => ({
    event_id: `evt_${index + 1}`, event_seq: index + 1, event_type: 'command_accepted', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-10-06T00:00:00Z', visibility: 'public',
    turn_id: `turn_${index + 1}`, attempt_id: `attempt_${index + 1}`,
    model_context_id: context.id, selection_revision: context.selection_revision,
    payload: { command_id: `cmd_${index + 1}`, kind: 'send_auto', payload: { text: `question ${index + 1}` } },
  }))
  const forward = vi.fn()
  const history = vi.fn(async (_id: string, before?: number) => {
    const cursor = before ?? 11
    const selected = events.filter((e) => e.event_seq < cursor).slice(-2)
    return { schema: 'capstone-thread-history/1', thread_id: 'thr_demo_39', before_event_seq: cursor,
      next_before_event_seq: selected[0]?.event_seq ?? cursor, has_more: selected[0]?.event_seq > 1, events: selected }
  })
  const store = new ThreadProjectionStore(new CapstoneThreadClient({
    ...createFixtureTransport(idleFixture), getSnapshot: async () => ({ ...idleFixture.snapshot, last_event_seq: 10 }),
    readEvents: forward, readHistory: history,
  }))
  await store.load('thr_demo_39')
  expect(forward).not.toHaveBeenCalled()
  expect(store.publicEvents.map((e) => e.eventSeq)).toEqual([9, 10])
  expect(store.state.hasOlderHistory).toBe(true)
  await store.loadOlderHistory()
  expect(store.publicEvents.map((e) => e.eventSeq)).toEqual([7, 8, 9, 10])
  expect(store.state.eventSeq).toBe(10)
})

it('catches up a workspace projection ahead of the loaded snapshot before exposing model controls', async () => {
  const nextContext = { ...context, id: 'ctx_case57', model_id: 'case57' }
  const event = { event_id: 'evt_switch', event_seq: 1, event_type: 'model_context_activated', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', model_context_id: nextContext.id,
    occurred_at: '2026-10-08T00:00:00Z', visibility: 'public',
    payload: { model_context: nextContext, active_grid_page_id: 'page_case57', previous_context: context, previous_grid_page_id: 'page_ieee39' } }
  const transport = createFixtureTransport(idleFixture)
  const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...transport,
    readEvents: async (_threadId, after) => ({ schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: after,
      next_event_seq: 1, has_more: false, events: after < 1 ? [event] : [] }),
    getModels: async () => ({ schema: 'capstone-thread-model-workspace/1', thread_id: 'thr_demo_39', run_id: 'run_001',
      event_seq: 1, current_entry_id: 'mdl_case57', blocked_reason: null, models: [{ entry_id: 'mdl_case57', model_id: 'case57',
        model_revision: '7', implementation_family: 'pandapower', authority_model_ref: 'gridctl:case57', display_name: 'case57',
        diagram_provider_id: 'gridctl', last_active_seq: 1 }] }),
  }))
  await store.load('thr_demo_39')
  expect(store.state.eventSeq).toBe(1)
  expect(store.state.snapshot?.activeModelContext.id).toBe('ctx_case57')
  expect(store.state.modelWorkspace?.currentEntryId).toBe('mdl_case57')
})

it('recovers a lost model-control receipt with its original identity and one activation', async () => {
  const nextContext = { ...context, id: 'ctx_case57', model_id: 'case57' }
  const command: ThreadCommand = { schema: 'capstone-command/1', thread_id: 'thr_demo_39', run_id: 'run_001',
    command_id: 'cmd_lost_model', idempotency_key: 'idem_lost_model', kind: 'activate_model', expected_event_seq: 0,
    payload: { entry_id: 'mdl_case57' } }
  let committed = false
  const transport = createFixtureTransport(idleFixture)
  const event = { event_id: 'evt_switch', event_seq: 1, event_type: 'model_context_activated', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', model_context_id: nextContext.id, occurred_at: '2026-10-08T00:00:00Z', visibility: 'public',
    payload: { model_context: nextContext, active_grid_page_id: 'page_case57', previous_context: context, previous_grid_page_id: 'page_ieee39' } }
  const sendCommand = vi.fn(async (submitted: ThreadCommand) => {
    expect(submitted).toEqual(command)
    if (!committed) { committed = true; throw new Error('response lost after commit') }
    return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id, command_id: command.command_id,
      idempotency_key: command.idempotency_key, status: 'accepted', accepted_event_seq: 1 }
  })
  const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...transport, sendCommand,
    getSnapshot: async () => ({ ...idleFixture.snapshot, active_model_context: committed ? nextContext : context,
      active_grid_page_id: committed ? 'page_case57' : 'page_ieee39', last_event_seq: committed ? 1 : 0 }),
    readEvents: async (_id, after) => ({ schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: after,
      next_event_seq: committed ? 1 : 0, has_more: false, events: committed && after < 1 ? [event] : [] }),
    getModels: async () => ({ schema: 'capstone-thread-model-workspace/1', thread_id: 'thr_demo_39', run_id: 'run_001',
      event_seq: committed ? 1 : 0, current_entry_id: committed ? 'mdl_case57' : 'mdl_ieee39', blocked_reason: null,
      models: ['ieee39', 'case57'].map((model_id) => ({ entry_id: `mdl_${model_id}`, model_id, model_revision: '7',
        implementation_family: 'pandapower', authority_model_ref: `gridctl:${model_id}`, display_name: model_id, diagram_provider_id: 'gridctl', last_active_seq: 0 })) }),
  }))
  await store.load('thr_demo_39')
  await expect(store.dispatch(command)).rejects.toThrow('response lost')
  await store.load('thr_demo_39')
  expect(store.state.modelWorkspace?.currentEntryId).toBe('mdl_case57')
  expect((await store.dispatch(command)).status).toBe('accepted')
  expect(sendCommand).toHaveBeenCalledTimes(2)
  expect(store.publicEvents.filter((item) => item.eventType === 'model_context_activated')).toHaveLength(1)
  expect(store.state.snapshot?.currentAttempt).toBeNull()
})

it('bounds a continuing stream and treats clean EOF as a reconnect without changing the live cursor', async () => {
  const store = new ThreadProjectionStore(new CapstoneThreadClient({
    ...createFixtureTransport(idleFixture),
    streamEvents: async function* () {
      for (let seq = 1; seq <= 1100; seq++) yield {
        eventId: `evt_${seq}`, eventSeq: seq, eventType: 'assistant_text_delta', eventVersion: 1,
        threadId: 'thr_demo_39', runId: 'run_001', occurredAt: '2026-10-06T00:00:00Z',
        visibility: 'public' as const, payload: { text: `message ${seq}` },
      }
    },
  }))
  await store.load('thr_demo_39')
  await expect(store.consumeEvents(new AbortController().signal)).rejects.toThrow('实时连接已关闭')
  expect(store.state.eventSeq).toBe(1100)
  expect(store.publicEvents).toHaveLength(1024)
  expect(store.publicEvents[0].eventSeq).toBe(77)
  expect(store.state.hasOlderHistory).toBe(true)
  expect(store.state.connection).toBe('reconnecting')
})

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

it('shares immutable geometry between repeated instructions while retaining every event and task', async () => {
  const events = [1, 2, 3, 4].map((seq) => ({
    event_id: `evt_${seq}`, event_seq: seq,
    event_type: seq % 2 ? 'network_diagram' : 'network_layer', event_version: 1,
    thread_id: 'thr_demo_39', run_id: 'run_001', attempt_id: seq < 3 ? 'attempt_a' : 'attempt_b',
    model_context_id: context.id, occurred_at: '2026-09-30T00:00:00Z', visibility: 'public',
    payload: seq % 2 ? { diagram: structuredClone(dynamicDiagram) } : { ordinal: 1, layer: dynamicLayer },
  }))
  const fixture = { ...idleFixture, snapshot: { ...idleFixture.snapshot, last_event_seq: 4 },
    events: { ...idleFixture.events, next_event_seq: 4, events } }
  const store = new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))
  await store.load('thr_demo_39')
  expect(store.publicEvents).toHaveLength(4)
  expect(store.networkTasks).toHaveLength(2)
  expect(store.networkTasks[0].view.diagram).toBe(store.networkTasks[1].view.diagram)
  const diagrams = store.publicEvents.filter((event) => event.eventType === 'network_diagram')
  expect(diagrams[0].payload.diagram).toBe(diagrams[1].payload.diagram)
})

function command(): ThreadCommand {
  return {
    schema: 'capstone-command/1', command_id: 'cmd_1', idempotency_key: 'idem_1',
    thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'cancel_live_attempt',
    expected_event_seq: 0, payload: { attempt_id: 'attempt_004a' },
  }
}

describe('ThreadProjectionStore', () => {
  it('keeps the same Thread snapshot visible while reconnecting', async () => {
    let finish!: (value: unknown) => void
    let loads = 0
    const store = new ThreadProjectionStore(new CapstoneThreadClient({
      ...createFixtureTransport(idleFixture),
      getSnapshot: async () => ++loads === 1 ? idleFixture.snapshot : new Promise((resolve) => { finish = resolve }),
    }))
    await store.load('thr_demo_39')
    const snapshot = store.state.snapshot
    const reconnect = store.load('thr_demo_39')
    expect(store.state.snapshot).toBe(snapshot)
    expect(store.state.connection).toBe('connecting')
    finish(idleFixture.snapshot)
    await reconnect
  })

  it('keeps an accepted receipt when its subsequent event read fails', async () => {
    const store = new ThreadProjectionStore(new CapstoneThreadClient({
      ...createFixtureTransport(idleFixture),
      readEvents: async () => { throw new Error('event connection lost') },
    }))
    await store.load('thr_demo_39')
    await expect(store.dispatch(command())).resolves.toMatchObject({ status: 'accepted' })
    expect(store.state.pendingCommands[0].receipt?.status).toBe('accepted')
    expect(store.state.connection).toBe('reconnecting')
  })

  it('blocks a fresh command while a previous receipt is unknown but permits its exact replay', async () => {
    let sends = 0
    const transport = createFixtureTransport(idleFixture)
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...transport,
      sendCommand: async (value) => {
        if (++sends === 1) throw new Error('receipt lost')
        return transport.sendCommand(value)
      },
    }))
    await store.load('thr_demo_39')
    await expect(store.dispatch(command())).rejects.toThrow('receipt lost')
    await store.load('thr_demo_39')
    await expect(store.dispatch({ ...command(), command_id: 'cmd_new', idempotency_key: 'idem_new' }))
      .rejects.toThrow('previous command receipt is unresolved')
    expect(sends).toBe(1)
    await expect(store.dispatch(command())).resolves.toMatchObject({ status: 'accepted' })
    expect(store.state.pendingCommands).toHaveLength(1)
  })
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
    const failedDiagram = { ...dynamicDiagram, model: { ...dynamicDiagram.model, id: nextContext.model_id }, ref: `diagram:sha256:${'c'.repeat(64)}` }
    const events = [
      ['network_diagram', context.id, { diagram: dynamicDiagram }],
      ['network_layer', context.id, { ordinal: 1, layer: dynamicLayer }],
      [changeType, nextContext.id, { model_context: nextContext, previous_context: context, active_grid_page_id: changeType === 'model_context_activated' ? 'page_pypsa39' : 'page_ieee39', previous_grid_page_id: 'page_ieee39' }],
      ['network_diagram', nextContext.id, { diagram: failedDiagram }],
      ['network_layer', nextContext.id, { ordinal: 1, layer: { ...dynamicLayer, diagram_ref: failedDiagram.ref, focus_ids: [] } }],
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
    expect(store.state.networkView?.diagram.ref).toBe(dynamicDiagram.ref)
    expect(store.state.networkView?.layer.focus_ids).toEqual(dynamicLayer.focus_ids)
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

    expect(store.state.gridPages.map((page) => page.pageId)).toEqual(['page_ctx_ieee_old', 'page_regional-six-bus', 'page_ieee39'])
    expect(store.state.gridPages.find((page) => page.context.id === historyContexts.initial.id)?.networkView?.diagram.model.id).toBe('ieee39')
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

  it('restores a closed model baseline from its exact Context without activating it', async () => {
    const historical = historyContexts.historical
    const snapshotBefore = structuredClone(idleFixture.snapshot)
    const diagram = { ...sampleDiagramView.diagram, model: { id: historical.model_id, revision: historical.model_revision, source: 'pypsamodelctl' } }
    const readNetworkEvents = vi.fn(async (_threadId: string, _signal?: AbortSignal, contextId?: string) => {
      if (!contextId) return { schema: 'capstone-thread-network-events/1', thread_id: 'thr_demo_39', model_context_id: context.id, events: [] }
      expect(contextId).toBe(historical.id)
      return { schema: 'capstone-thread-network-events/1', thread_id: 'thr_demo_39', model_context_id: historical.id,
        model_context: historical, events: [{ event_id: 'evt_closed_diagram', event_seq: 1, event_type: 'network_diagram', event_version: 1,
          thread_id: 'thr_demo_39', run_id: 'run_001', model_context_id: historical.id, occurred_at: '2026-10-08T00:00:00Z', visibility: 'public', payload: { diagram } }] }
    })
    const store = new ThreadProjectionStore(new CapstoneThreadClient({ ...createFixtureTransport(idleFixture), readNetworkEvents }))
    await store.load('thr_demo_39')
    const pageId = await store.restoreHistoricalNetwork(historical.id, 'attempt_closed')
    expect(pageId).toBe(`page_${historical.id}`)
    expect(store.state.snapshot?.toDocument()).toEqual(snapshotBefore)
    expect(store.networkTasks.find((task) => task.attemptId === 'attempt_closed')?.view.diagram.model.revision).toBe(historical.model_revision)
    expect(store.state.pendingCommands).toEqual([])
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

    expect(store.state.gridPages).toHaveLength(4)
    expect(store.state.gridPages.find((page) => page.context.id === historyContexts.historical.id)?.networkView?.diagram.model.id).toBe('regional-six-bus')
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
    expect(store.state.gridPages.map((page) => page.pageId)).toEqual(['page_ctx_ieee_old', 'page_regional-six-bus', 'page_ieee39', 'page_pypsa39'])
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
