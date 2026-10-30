import { afterEach, expect, it, vi } from 'vitest'
import { CapstoneThreadClient, type ThreadTransport } from './threadClient'
import { ThreadProjectionStore } from './threadProjectionStore'
import { parseEventEnvelope } from './threadProtocol'
import { buildStartWorkCommand } from './threadWorkProtocol'
import { projectWorkConversation } from './threadWorkMessages'

afterEach(() => sessionStorage.clear())

function workSnapshot() {
  return { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work', run: { run_id: 'run_work', state: 'open' },
    active_model_context: null, active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] as unknown[] }
}

function work(revision = 1, status = 'ready') {
  return { work_id: 'work_one', goal: '真实任务', goal_revision: 1, revision, status, blocked_reason: null,
    latest_attempt_id: status === 'ready' ? null : 'attempt_one', start_available: status === 'ready',
    start_unavailable_reason: status === 'ready' ? null : 'attempt_in_progress', messages: ['真实任务'],
    task_context: { binding: { thread_id: 'thr_work', work_id: 'work_one', research_id: 'research-one' },
      goal_revision: 1, snapshot_id: 'task_one', model_contexts: [], resource_refs: [] } }
}
function event(seq: number, row = work(seq + 1, 'running')) {
  return { event_id: `evt_${seq}`, event_seq: seq, event_type: 'command.applied', event_version: 2,
    thread_id: 'thr_work', run_id: 'run_work', occurred_at: '2026-10-17T00:00:00Z', visibility: 'public',
    payload: { command_id: 'cmd_start', work_id: 'work_one', work: row } }
}
function transport(extra: Partial<ThreadTransport> = {}): ThreadTransport {
  return { getSnapshot: async () => ({ ...workSnapshot(), works: [work()] }),
    readEvents: async (_id, after) => ({ schema: 'capstone-thread-events/1', thread_id: 'thr_work', after_event_seq: after,
      next_event_seq: after, has_more: false, events: [] }), sendCommand: vi.fn(), ...extra }
}

it('keeps consuming execution events while an authority snapshot read is pending',async()=>{
  let reads=0
  const rows=[event(1),{...event(2),event_type:'runtime_action',payload:{phase:'started'}}]
  const store=new ThreadProjectionStore(new CapstoneThreadClient(transport({
    getSnapshot:async()=>++reads===1?{...workSnapshot(),works:[work()]}:new Promise(()=>{}),
    streamEvents:async function*(){for(const row of rows)yield parseEventEnvelope(row)},
  })),undefined,{protocolVersion:'2'})
  await store.load('thr_work')
  void store.consumeEvents()
  await vi.waitFor(()=>expect(store.state.eventSeq).toBe(2),{timeout:100})
  expect(store.publicEvents.some(row=>row.eventType==='runtime_action')).toBe(true)
})

it('bounds snapshot synchronization including a pending event catch-up',async()=>{
  const deadline=new AbortController()
  const timeout=vi.spyOn(AbortSignal,'timeout').mockReturnValue(deadline.signal)
  let reads=0,catchUpSignal:AbortSignal|null|undefined
  const store=new ThreadProjectionStore(new CapstoneThreadClient(transport({
    getSnapshot:async()=>({...workSnapshot(),last_event_seq:++reads===1?0:1,works:[work()]}),
    readEvents:async(_id,_after,signal)=>{catchUpSignal=signal;return new Promise((_,reject)=>signal?.addEventListener('abort',()=>reject(signal.reason),{once:true}))},
  })),undefined,{protocolVersion:'2'})
  try{
    await store.load('thr_work')
    const refresh=store.refreshWorkSnapshot()
    const rejected=expect(refresh).rejects.toThrow('status deadline')
    await vi.waitFor(()=>expect(catchUpSignal).toBe(deadline.signal))
    deadline.abort(new Error('status deadline'))
    await rejected
    expect(timeout).toHaveBeenCalled()
  }finally{timeout.mockRestore()}
})

it('uses the same event store for v2 snapshots, stream deduplication and live Work status', async () => {
  const stream = event(1)
  let live = false
  const store = new ThreadProjectionStore(new CapstoneThreadClient(transport({
    getSnapshot: async () => ({ ...workSnapshot(), last_event_seq: live ? 1 : 0, works: [work(live ? 2 : 1, live ? 'running' : 'ready')] }),
    streamEvents: async function* () { live = true; yield parseEventEnvelope(stream); yield parseEventEnvelope(stream) },
  })), 'work-store', { protocolVersion: '2' })
  await store.load('thr_work')
  expect(store.state.snapshot).toBeNull()
  expect(store.state.workSnapshot?.works[0].status).toBe('ready')
  await store.consumeEvents()
  expect(store.state.workSnapshot?.works[0].status).toBe('running')
  expect(store.state.eventSeq).toBe(1)
  expect(store.publicEvents).toHaveLength(1)
})

it('refreshes every Work availability at a terminal boundary and admits a snapshot ahead of the stream once', async () => {
  const b = { ...work(), work_id: 'work_b', start_available: false, start_unavailable_reason: 'attempt_in_progress',
    task_context: { ...work().task_context, binding: { ...work().task_context.binding, work_id: 'work_b' } } }
  const readyB = { ...b, start_available: true, start_unavailable_reason: null }
  const finished = { ...work(3, 'completed'), start_available: true, start_unavailable_reason: null }
  const terminal = { ...event(1, finished), event_type: 'attempt_completed', attempt_id: 'attempt_one' }
  const progress = { ...event(2), event_type: 'agent_phase', payload: {} }
  const otherWork = { ...event(3, readyB), payload: { command_id: 'cmd_other', work_id: 'work_b', work: readyB } }
  const rows = [terminal, progress, otherWork]
  let live = false
  const store = new ThreadProjectionStore(new CapstoneThreadClient(transport({
    getSnapshot: async () => ({ ...workSnapshot(), last_event_seq: live ? 3 : 0, works: live ? [finished, readyB] : [work(2, 'running'), b] }),
    readEvents: async (_id, after) => ({ schema: 'capstone-thread-events/1', thread_id: 'thr_work', after_event_seq: after,
      next_event_seq: 3, has_more: false, events: rows.filter(row => row.event_seq > after) }),
    streamEvents: async function* () { live = true; for (const row of rows) yield parseEventEnvelope(row) },
  })), undefined, { protocolVersion: '2' })
  await store.load('thr_work')
  expect(store.state.workSnapshot?.works[1].startAvailable).toBe(false)
  await store.consumeEvents()
  expect(store.state.workSnapshot?.works[1].startAvailable).toBe(true)
  expect(store.state.eventSeq).toBe(3)
  expect(store.publicEvents.map(row => row.eventSeq)).toEqual([1, 2, 3])
})

it('persists a lost start command and restores its exact identity without a refresh write', async () => {
  const send = vi.fn(async () => { throw new Error('response lost') })
  const client = new CapstoneThreadClient(transport({ sendWorkCommand: send }))
  const store = new ThreadProjectionStore(client, 'start-recovery', { protocolVersion: '2' })
  await store.load('thr_work')
  const command = buildStartWorkCommand('thr_work', 'run_work', 'cmd_start', 'idem_start', 'work_one', 1)
  await expect(store.dispatch(command)).rejects.toThrow('response lost')
  const restored = new ThreadProjectionStore(client, 'start-recovery', { protocolVersion: '2' })
  await restored.load('thr_work')
  expect(send).toHaveBeenCalledTimes(1)
  expect(restored.state.pendingCommands[0].command).toEqual(command)
})

it('preserves two complete native turns across streaming and refresh with no professional snapshot', async () => {
  const rows: Array<Omit<ReturnType<typeof event>, 'payload'> & {
    payload: Record<string, unknown>; attempt_id: string; turn_id: string
  }> = []
  for (let turn = 0; turn < 2; turn++) {
    const identity = {attempt_id: `attempt_${turn}`, turn_id: `turn_${turn}`}
    rows.push({...event(rows.length + 1), ...identity, event_type: 'command_accepted', event_version: 1,
      payload: {kind: 'send_auto', payload: {text: `用户${turn}`}, work_id: 'work_one'}})
    rows.push({...event(rows.length + 1), ...identity, event_type: 'attempt_started', event_version: 1,
      payload: {work_id: 'work_one'}})
    rows.push({...event(rows.length + 1), ...identity, event_type: 'assistant_text_delta', event_version: 1,
      payload: {text: '部分答复'}})
    rows.push({...event(rows.length + 1), ...identity, event_type: 'attempt_completed', event_version: 1,
      payload: {work_id: 'work_one', answer: `完整${turn}`}})
  }
  let cursor = 0
  const readSnapshot = () => ({...workSnapshot(), last_event_seq: cursor, runtime_mode: 'capstone',
    native_execution: {available: true, unavailable_reason: null},
    works: [{...work(3 + cursor, cursor ? 'completed' : 'ready'), conversation_mode: true, messages: []}]})
  const connection = transport({getSnapshot: async () => readSnapshot(),
    readEvents: async (_id, after) => ({schema: 'capstone-thread-events/1', thread_id: 'thr_work',
      after_event_seq: after, next_event_seq: cursor, has_more: false, events: rows.filter(row => row.event_seq > after && row.event_seq <= cursor)}),
    streamEvents: async function* () {for (const row of rows) {cursor = row.event_seq; yield parseEventEnvelope(row)}}})
  const store = new ThreadProjectionStore(new CapstoneThreadClient(connection), undefined, {protocolVersion: '2'})
  await store.load('thr_work')
  await store.consumeEvents()
  const render = (value: ThreadProjectionStore) => projectWorkConversation(value.publicEvents,
    value.state.workSnapshot!.works[0], value.state.workSnapshot!.works).messages
  expect(store.state.snapshot).toBeNull()
  expect(store.state.workSnapshot?.currentAttempt).toBeNull()
  expect(store.state.eventSeq).toBe(8)
  expect(render(store).map(message => message.role)).toEqual(['user', 'assistant', 'user', 'assistant'])
  const restored = new ThreadProjectionStore(new CapstoneThreadClient(connection), undefined, {protocolVersion: '2'})
  await restored.load('thr_work')
  expect(render(restored)).toEqual(render(store))
  expect(render(restored)[3].content).toEqual([{type: 'text', text: '完整1'}])
})

it('keeps an in-flight start under its original Thread when its view is disposed', async () => {
  let complete!: (value: unknown) => void
  const send = vi.fn(async () => new Promise(resolve => { complete = resolve }))
  const client = new CapstoneThreadClient(transport({ sendWorkCommand: send }))
  const a = new ThreadProjectionStore(client, 'thread-a', { protocolVersion: '2' })
  await a.load('thr_work')
  const command = buildStartWorkCommand('thr_work', 'run_work', 'cmd_start', 'idem_start', 'work_one', 1)
  const pending = a.dispatch(command)
  a.dispose()
  const b = new ThreadProjectionStore(new CapstoneThreadClient(transport({
    getSnapshot: async () => ({ ...workSnapshot(), thread_id: 'thr_b', run: { run_id: 'run_b', state: 'open' }, works: [] }),
  })), 'thread-b', { protocolVersion: '2' })
  await b.load('thr_b')
  complete({ schema: 'capstone-command-receipt/1', command_id: command.command_id, idempotency_key: command.idempotency_key,
    thread_id: 'thr_work', status: 'accepted', accepted_event_seq: 1 })
  await pending
  expect(b.state.workSnapshot?.threadId).toBe('thr_b')
  expect(b.state.pendingCommands).toEqual([])
  const restored = new ThreadProjectionStore(client, 'thread-a', { protocolVersion: '2' })
  await restored.load('thr_work')
  expect(restored.state.pendingCommands[0].command).toEqual(command)
  expect(send).toHaveBeenCalledTimes(1)
})
