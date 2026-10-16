import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadLiveEntry from './ThreadLiveEntry'
import type { WorkCommand } from './threadWorkProtocol'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); window.history.replaceState({}, '', '/') })

/** In-memory HTTP authority fixture. It never invokes a Provider or simulator. */
function authority({ lostStart = false, lostCancel = false, modelFree = false } = {}) {
  const model = { id: 'ctx_one', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`, implementation_family: 'pandapower', selection_revision: 'sel_one' }
  const context = { binding: { thread_id: 'thr_work', work_id: 'work_one', research_id: 'research-one' }, goal_revision: 1,
    snapshot_id: 'task_one', model_contexts: modelFree ? [] : [model], resource_refs: [] }
  const work = { work_id: 'work_one', goal: '测试目标', goal_revision: 1, revision: 1, status: modelFree ? 'blocked' : 'ready',
    blocked_reason: modelFree ? 'execution_unavailable' : null, latest_attempt_id: null as string | null,
    cancel_requested: false, messages: ['测试目标'], task_context: context }
  let upgraded = modelFree
  let saved = modelFree
  let attempt: Record<string, unknown> | null = null
  let stream: ReadableStreamDefaultController<Uint8Array> | undefined
  const events: Record<string, unknown>[] = []
  const projections: Record<string, unknown>[] = []
  const receipts = new Map<string, Record<string, unknown>>()
  const commands: WorkCommand[] = []
  let attemptsCreated = 0
  let snapshots = 0
  function projection() {
    const reason = modelFree ? 'execution_unavailable' : attempt ? 'attempt_in_progress' : null
    return { ...work, start_available: reason === null, start_unavailable_reason: reason }
  }
  function snapshot() {
    const base = { schema: 'capstone-thread-snapshot/1', thread_id: 'thr_work', run: { run_id: 'run_work', state: 'open' },
      active_model_context: modelFree ? null : model, active_grid_page_id: modelFree ? null : 'page_one', current_attempt: attempt,
      last_event_seq: events.length, base_event_seq: 0, result_projections: projections }
    return upgraded ? { ...base, schema: 'capstone-thread-snapshot/2', minimum_protocol_version: 2,
      selected_model_context_id: modelFree ? null : model.id, works: saved ? [projection()] : [], task_context: saved ? context : null } : base
  }
  function append(type: string, payload: Record<string, unknown>, withAttempt = false) {
    const event = { event_id: `evt_${events.length + 1}`, event_seq: events.length + 1, event_type: type, event_version: 2,
      thread_id: 'thr_work', run_id: 'run_work', occurred_at: '2026-10-17T00:00:00Z', visibility: 'public', payload,
      ...(withAttempt ? { attempt_id: 'attempt_one', turn_id: 'turn_one', model_context_id: 'ctx_one', selection_revision: 'sel_one' } : {}) }
    events.push(event)
    try { stream?.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`)) }
    catch { /* Durable server events remain readable when the client stream has disconnected. */ }
    return event.event_seq
  }
  function started() {
    work.status = 'running'; work.revision += 1; attempt = { ...attempt, phase: 'running' }
    append('attempt_started', { work_id: work.work_id, work: projection() }, true)
  }
  function finish(cancelled = false) {
    work.status = cancelled ? 'cancelled' : 'completed'; work.revision += 1; work.cancel_requested = false; attempt = null
    const result = { schema: 'capstone-result-projection/1.0', result_id: 'result_one',
      result_ref: `result:sha256:${'a'.repeat(64)}`, evidence_refs: [`evidence:sha256:${'b'.repeat(64)}`],
      thread_id: 'thr_work', run_id: 'run_work', turn_id: 'turn_one', attempt_id: 'attempt_one',
      model_context_id: 'ctx_one', model_id: 'ieee39', model_revision: model.model_revision,
      source: { capability_id: 'analysis.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
      status: 'completed', summary: [], tables: [], element_refs: [], overlay: null }
    if (!cancelled) projections.push(result)
    append(cancelled ? 'attempt_cancelled' : 'attempt_completed', { work_id: work.work_id, work: projection(),
      ...(cancelled ? { reason: 'user_requested' } : { answer: '来自真实事件的测试结果', result_projections: [result] }) }, true)
  }
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
    const parsed = new URL(String(url), 'http://localhost')
    if (parsed.pathname.endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (parsed.pathname.endsWith('/threads') && init?.method !== 'POST') return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (parsed.pathname.endsWith('/history')) {
      const before = Number(parsed.searchParams.get('before') || events.length + 1)
      return response({ schema: 'capstone-thread-history/1', thread_id: 'thr_work', before_event_seq: before,
        next_before_event_seq: 1, has_more: false, events: events.filter(row => Number(row.event_seq) < before) })
    }
    if (parsed.pathname.endsWith('/events/stream')) return new Response(new ReadableStream<Uint8Array>({
      start(controller) { stream = controller; init?.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), { once: true }) },
    }), { headers: { 'Capstone-Thread-Version': '2' } })
    if (parsed.pathname.endsWith('/events')) {
      const after = Number(parsed.searchParams.get('after') || 0)
      return response({ schema: 'capstone-thread-events/1', thread_id: 'thr_work', after_event_seq: after,
        next_event_seq: events.length, has_more: false, events: events.filter(row => Number(row.event_seq) > after) })
    }
    if (parsed.pathname.endsWith('/commands')) {
      const command = JSON.parse(String(init?.body)) as WorkCommand; commands.push(command)
      const previous = receipts.get(command.idempotency_key)
      if (previous) return response(previous)
      if (command.kind === 'work_message') { upgraded = true; saved = true }
      if (command.kind === 'start_work') {
        attemptsCreated += 1; work.status = 'queued'; work.revision += 1; work.latest_attempt_id = 'attempt_one'
        attempt = { attempt_id: 'attempt_one', turn_id: 'turn_one', target_model_context_id: model.id, phase: 'accepted', runtime_mode: 'capstone' }
      }
      if (command.kind === 'cancel_work') { work.cancel_requested = true; work.revision += 1 }
      const accepted = append('command.applied', { command_id: command.command_id, work_id: work.work_id, work: projection() })
      if (command.kind === 'start_work') append('command_accepted', { kind: 'send_auto', payload: { text: work.goal }, work_id: work.work_id, work: projection() }, true)
      if (command.kind === 'cancel_work') append('attempt_cancel_requested', { work_id: work.work_id, work: projection() }, true)
      const receipt = { schema: 'capstone-command-receipt/1', command_id: command.command_id, idempotency_key: command.idempotency_key,
        thread_id: 'thr_work', status: 'accepted', accepted_event_seq: accepted, target: { kind: 'work', id: work.work_id,
          expected_revision: work.revision, ...(attempt ? { turn_id: 'turn_one', attempt_id: 'attempt_one' } : {}) } }
      receipts.set(command.idempotency_key, receipt)
      if (command.kind === 'start_work' && lostStart) throw new TypeError('start response lost')
      if (command.kind === 'cancel_work' && lostCancel) throw new TypeError('cancel response lost')
      return response(receipt)
    }
    if (parsed.pathname.endsWith('/thr_work')) { snapshots += 1; return response(snapshot()) }
    if (parsed.pathname.endsWith('/catalog')) return response({ schema: 'capstone-thread-catalog/1', models: [], profiles: [] })
    throw new Error(`Unexpected test request: ${parsed.pathname}`)
  })
  return { fetcher, commands, started, finish, snapshot, work, get upgraded() { return upgraded },
    get attemptsCreated() { return attemptsCreated }, get snapshots() { return snapshots }, get streamReady() { return stream !== undefined },
    disconnect() { stream?.error(new TypeError('stream disconnected')) } }
}

async function saveGoal(server: ReturnType<typeof authority>) {
  vi.stubGlobal('fetch', server.fetcher)
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: '测试目标' } })
  expect(server.upgraded).toBe(false)
  expect(server.commands).toHaveLength(0)
  await waitFor(() => expect(server.streamReady).toBe(true))
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByRole('textbox', { name: '补充任务资料' })
  await waitFor(() => expect((screen.getByRole('button', { name: '开始任务' }) as HTMLButtonElement).disabled).toBe(false))
}

it('reads a real v1 Thread, upgrades only on Work save, and displays streamed execution and results', async () => {
  const server = authority()
  await saveGoal(server)
  expect(server.upgraded).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByText('修订 1 · 已排队')
  expect(server.commands[1].kind).toBe('start_work')
  expect(server.commands[1].payload).toEqual({})
  await act(async () => server.started())
  await screen.findByText('修订 1 · 执行中')
  await act(async () => server.finish())
  expect(screen.queryByRole('alert')?.textContent).toBeUndefined()
  await screen.findByText('来自真实事件的测试结果')
  expect(screen.getByText('修订 1 · 已完成')).toBeTruthy()
  expect(document.querySelectorAll('.capstone-chat-message.is-user')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: '查看计算结果' }))
  expect(await screen.findByRole('region', { name: '结构化计算结果' })).toBeTruthy()
  const reads = server.snapshots
  await act(async () => server.disconnect())
  await waitFor(() => expect(server.snapshots).toBeGreaterThan(reads), { timeout: 3000 })
  expect(server.commands).toHaveLength(2)
  expect(screen.getAllByText('来自真实事件的测试结果')).toHaveLength(1)
})

it('recovers a lost start receipt with the exact key and creates one Attempt', async () => {
  const server = authority({ lostStart: true })
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '重试执行请求' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '重试执行请求' }))
  await screen.findByText('执行请求已接收；排队、执行与结果以实际任务状态为准。')
  const starts = server.commands.filter(command => command.kind === 'start_work')
  expect(starts).toHaveLength(2); expect(starts[1]).toEqual(starts[0]); expect(server.attemptsCreated).toBe(1)
})

it('uses the shared stop action and waits for the real terminal event', async () => {
  const server = authority()
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByRole('button', { name: '停止任务' })
  await act(async () => server.started())
  fireEvent.click(screen.getByRole('button', { name: '停止任务' }))
  await screen.findByText('修订 1 · 停止请求中')
  expect(server.commands.at(-1)?.kind).toBe('cancel_work')
  expect(screen.queryByText('修订 1 · 已取消')).toBeNull()
  expect((screen.getByRole('button', { name: '停止请求中' }) as HTMLButtonElement).disabled).toBe(true)
  await act(async () => server.finish(true))
  await screen.findByText('修订 1 · 已取消')
})

it('shows a readable unavailable reason for a model-free Work without starting it', async () => {
  const server = authority({ modelFree: true })
  vi.stubGlobal('fetch', server.fetcher)
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.click(await screen.findByRole('button', { name: '01 · 测试目标' }))
  expect((screen.getByRole('button', { name: '开始任务' }) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getByText('当前任务的执行能力尚未接通，仍可保存目标和资料。')).toBeTruthy()
  expect(server.commands).toHaveLength(0)
})

it('recovers a lost stop receipt with the same target and key without repeating the state change', async () => {
  const server = authority({ lostCancel: true })
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByRole('button', { name: '停止任务' })
  await act(async () => server.started())
  const before = server.work.revision
  fireEvent.click(screen.getByRole('button', { name: '停止任务' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '重试停止请求' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '重试停止请求' }))
  await screen.findByText('停止请求已接收，正在等待实际执行停止。')
  const cancels = server.commands.filter(command => command.kind === 'cancel_work')
  expect(cancels).toHaveLength(2); expect(cancels[1]).toEqual(cancels[0])
  expect(server.work.revision).toBe(before + 1)
  expect(server.work.status).toBe('running')
  await act(async () => server.finish(true))
  await screen.findByText('修订 1 · 已取消')
})

it('can resolve the original lost stop receipt after the real terminal state has arrived', async () => {
  const server = authority({ lostCancel: true })
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByRole('button', { name: '停止任务' })
  await act(async () => server.started())
  fireEvent.click(screen.getByRole('button', { name: '停止任务' }))
  await screen.findByRole('button', { name: '重试停止请求' })
  await act(async () => server.finish(true))
  await screen.findByText('修订 1 · 已取消')
  await waitFor(() => expect((screen.getByRole('button', { name: '重试停止请求' }) as HTMLButtonElement).disabled).toBe(false))
  const terminalRevision = server.work.revision
  fireEvent.click(screen.getByRole('button', { name: '重试停止请求' }))
  await screen.findByText('停止请求已确认。')
  expect(screen.queryByRole('button', { name: '重试停止请求' })).toBeNull()
  expect((screen.getByRole('button', { name: '开始任务' }) as HTMLButtonElement).disabled).toBe(false)
  const cancels = server.commands.filter(command => command.kind === 'cancel_work')
  expect(cancels).toHaveLength(2); expect(cancels[1]).toEqual(cancels[0])
  expect(server.work.revision).toBe(terminalRevision)
})
