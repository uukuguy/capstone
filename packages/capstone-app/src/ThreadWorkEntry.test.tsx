import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadLiveEntry from './ThreadLiveEntry'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); window.history.replaceState({}, '', '/') })

it('keeps professional history readable after the same Thread upgrades to Work', async () => {
  const snapshot = { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: { id: 'ctx_one', model_id: 'ieee39',
      model_revision: '1', implementation_family: 'pandapower', selection_revision: 'sel_one' },
    active_grid_page_id: 'page_ieee39', current_attempt: null, last_event_seq: 2, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: 'ctx_one', task_context: null, works: [] }
  const events = [ ['command_accepted', { kind: 'send_auto', text: '旧专业任务' }], ['attempt_completed', { answer: '旧专业结论仍可读取' }] ]
    .map(([event_type, payload], index) => ({ event_id: `evt_${index}`, event_seq: index + 1, event_type, payload,
      event_version: 1, thread_id: 'thr_work', run_id: 'run_work', turn_id: 'turn_one', attempt_id: 'attempt_one',
      model_context_id: 'ctx_one', occurred_at: '2026-10-16T00:00:00Z', visibility: 'public' }))
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL) => {
    if (String(url).endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (String(url).includes('/threads?')) return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (String(url).includes('/history?')) return response({ schema: 'capstone-thread-history/1', thread_id: 'thr_work',
      before_event_seq: 3, next_before_event_seq: 1, has_more: false, events })
    return response(snapshot)
  }))
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  expect(await screen.findByText('旧专业结论仍可读取')).toBeTruthy()
  expect(screen.queryByRole('textbox', { name: 'Thread 指令' })).toBeNull()
})

it('opens and restores a model-free work without preparing grid workers or submitting on refresh', async () => {
  const snapshot = { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: null,
    active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] }
  const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith('/thread-access')) return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'open' }))
    if (String(url).includes('/threads?')) return new Response(JSON.stringify({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null }), { headers: { 'Capstone-Thread-Version': '2' } })
    if (init?.method === 'POST') expect(JSON.parse(String(init.body))).toEqual({})
    return new Response(JSON.stringify(snapshot), { headers: { 'Capstone-Thread-Version': '2' } })
  })
  vi.stubGlobal('fetch', fetcher)
  const first = render(<ThreadLiveEntry threadId="new" mode="work" />)
  fireEvent.click(await screen.findByRole('button', { name: '新建任务会话' }))
  await screen.findByRole('textbox', { name: '任务目标' })
  expect(fetcher.mock.calls.some(([url]) => String(url).includes('workbench-preparation'))).toBe(false)
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  first.unmount()
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  await waitFor(() => expect(screen.getByRole('textbox', { name: '任务目标' })).toBeTruthy())
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  expect(screen.getByText(/持续执行尚未接通/)).toBeTruthy()
})

it('keeps a lost-response command across refresh and retries its exact identity', async () => {
  const snapshot = { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: null,
    active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] }
  const commands: Record<string, unknown>[] = []
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (String(url).includes('/threads?')) return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (String(url).endsWith('/commands')) {
      const command = JSON.parse(String(init?.body)); commands.push(command)
      if (commands.length === 1) throw new Error('connection lost')
      return response({ schema: 'capstone-command-receipt/1', thread_id: 'thr_work', run_id: 'run_work',
        command_id: command.command_id, idempotency_key: command.idempotency_key, status: 'accepted', accepted_event_seq: 1 })
    }
    return response(snapshot)
  }))
  const first = render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: '汇总资料中的结论' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByText('connection lost')
  first.unmount()
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  await screen.findByRole('button', { name: '重试保存' })
  expect(commands).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: '重试保存' }))
  await screen.findByText('任务已保存。持续执行尚未接通，本次未启动分析。')
  expect(commands).toHaveLength(2)
  expect(commands[1]).toEqual(commands[0])
})

it('restores supplementary drafts under their original Work and releases a rejected request', async () => {
  const context = { binding: { thread_id: 'thr_work', work_id: 'work_one', research_id: 'research-one' },
    goal_revision: 1, snapshot_id: 'task_one', model_contexts: [], resource_refs: [] }
  const snapshot = { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: null,
    active_grid_page_id: null, current_attempt: null, last_event_seq: 1, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: context,
    works: [{ work_id: 'work_one', goal: '原目标', goal_revision: 1, revision: 1, status: 'blocked',
      blocked_reason: 'execution_unavailable', task_context: context, messages: ['原目标'] }] }
  const commands: Record<string, unknown>[] = []
  const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Capstone-Thread-Version': '2' } })
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (String(url).includes('/threads?')) return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (String(url).endsWith('/commands')) { commands.push(JSON.parse(String(init?.body))); return response({ error: 'invalid_command' }, 422) }
    return response(snapshot)
  }))
  const first = render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.click(await screen.findByRole('button', { name: '01 · 原目标' }))
  fireEvent.change(screen.getByRole('textbox', { name: '补充任务资料' }), { target: { value: '补充资料' } })
  fireEvent.click(screen.getByRole('button', { name: '新的任务目标' }))
  expect((screen.getByRole('textbox', { name: '任务目标' }) as HTMLTextAreaElement).value).toBe('')
  fireEvent.click(screen.getByRole('button', { name: '01 · 原目标' }))
  expect((screen.getByRole('textbox', { name: '补充任务资料' }) as HTMLTextAreaElement).value).toBe('补充资料')
  first.unmount()
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  expect((await screen.findByRole('textbox', { name: '补充任务资料' }) as HTMLTextAreaElement).value).toBe('补充资料')
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByRole('alert')
  expect(commands[0]?.target).toEqual({ kind: 'work', id: 'work_one', expected_revision: 1 })
  expect((screen.getByRole('textbox', { name: '补充任务资料' }) as HTMLTextAreaElement).disabled).toBe(false)
})
