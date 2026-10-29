import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadLiveEntry from './ThreadLiveEntry'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); window.history.replaceState({}, '', '/') })
it('returns to workspace selection when same-space navigation removes the thread parameter',async()=>{
  const snapshot={schema:'capstone-thread-snapshot/2',thread_id:'thr_a',run:{run_id:'run_a',state:'open'},active_model_context:null,active_grid_page_id:null,current_attempt:null,last_event_seq:0,base_event_seq:0,minimum_protocol_version:2,selected_model_context_id:null,task_context:null,works:[]}
  const response=(body:unknown)=>new Response(JSON.stringify(body),{headers:{'Capstone-Thread-Version':'2'}})
  const fetcher=vi.fn(async(url:string|URL)=>{
    if(String(url).endsWith('/thread-access'))return response({schema:'capstone-thread-access/1',mode:'open'})
    if(String(url).includes('/threads?'))return response({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null})
    return readFallback(url,snapshot)||response(snapshot)
  })
  vi.stubGlobal('fetch',fetcher)
  window.history.replaceState({},'','/?workspace=enterprise&thread=thr_a')
  render(<ThreadLiveEntry threadId="thr_a" presentation="workspace"/>)
  await waitFor(()=>expect(fetcher.mock.calls.some(call=>String(call[0]).endsWith('/thr_a'))).toBe(true))
  window.history.pushState({},'','/?workspace=enterprise');fireEvent.popState(window)
  expect(await screen.findByRole('heading',{name:'新建任务会话'})).toBeTruthy()
})

function readFallback(url: string | URL, snapshot: { last_event_seq: number }) {
  const parsed = new URL(String(url), 'http://localhost')
  const threadId = parsed.pathname.split('/')[4]
  const headers = { 'Capstone-Thread-Version': '2' }
  if (parsed.pathname.endsWith('/events/stream')) return new Response(new ReadableStream(), { headers })
  if (parsed.pathname.endsWith('/events')) {
    const after = Number(parsed.searchParams.get('after') || 0)
    return new Response(JSON.stringify({ schema: 'capstone-thread-events/1', thread_id: threadId,
      after_event_seq: after, next_event_seq: after, has_more: false, events: [] }), { headers })
  }
  if (parsed.pathname.endsWith('/history')) {
    const before = Number(parsed.searchParams.get('before') || snapshot.last_event_seq + 1)
    return new Response(JSON.stringify({ schema: 'capstone-thread-history/1', thread_id: threadId,
      before_event_seq: before, next_before_event_seq: before, has_more: false, events: [] }), { headers })
  }
  return null
}

it('keeps an uncertain save with its original Thread when navigation occurs before its response', async () => {
  const snapshot = (id: string) => ({ schema: 'capstone-thread-snapshot/2', thread_id: id,
    run: { run_id: `run_${id}`, state: 'open' }, active_model_context: null, active_grid_page_id: null,
    current_attempt: null, last_event_seq: 0, base_event_seq: 0, minimum_protocol_version: 2,
    selected_model_context_id: null, task_context: null, works: [] })
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  let complete!: (response: Response) => void
  let submitted: Record<string, unknown> = {}
  const commands: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (String(url).includes('/threads?')) return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (String(url).endsWith('/commands')) {
      submitted = JSON.parse(String(init?.body)); commands.push(submitted)
      return new Promise<Response>(resolve => { complete = resolve })
    }
    return readFallback(url, { last_event_seq: 0 }) || response(snapshot(String(url).endsWith('thr_b') ? 'thr_b' : 'thr_a'))
  }))
  window.history.replaceState({}, '', '/?workspace=enterprise&thread=thr_a')
  render(<ThreadLiveEntry threadId="thr_a" mode="work" />)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: 'A的目标' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await waitFor(() => expect(commands).toHaveLength(1))
  window.history.pushState({}, '', '/?workspace=enterprise&thread=thr_b'); fireEvent.popState(window)
  await waitFor(() => expect((screen.getByRole('textbox', { name: '任务目标' }) as HTMLTextAreaElement).value).toBe(''))
  fireEvent.change(screen.getByRole('textbox', { name: '任务目标' }), { target: { value: 'B的草稿' } })
  await act(async () => { complete(response({ schema: 'capstone-command-receipt/1', thread_id: 'thr_a', run_id: 'run_thr_a',
    command_id: submitted.command_id, idempotency_key: submitted.idempotency_key, status: 'accepted', accepted_event_seq: 1 })) })
  await waitFor(() => expect((screen.getByRole('textbox', { name: '任务目标' }) as HTMLTextAreaElement).value).toBe('B的草稿'))
  window.history.pushState({}, '', '/?workspace=enterprise&thread=thr_a'); fireEvent.popState(window)
  await screen.findByRole('button', { name: '重试保存' })
  expect(commands).toHaveLength(1)
  await waitFor(() => expect((screen.getByRole('textbox', { name: '任务目标' }) as HTMLTextAreaElement).value).toBe('A的目标'))
})

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
    return readFallback(url, snapshot) || response(snapshot)
  }))
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  expect(await screen.findByText('旧专业结论仍可读取')).toBeTruthy()
  expect(screen.getAllByTestId('assistant-ui-chat')).toHaveLength(1)
  expect(screen.getByRole('textbox', { name: '任务目标' })).toBeTruthy()
  expect(screen.queryByRole('textbox', { name: 'Thread 指令' })).toBeNull()
})

it('selects the server-assigned Work after saving and sends supplements to that same Work', async () => {
  const context = { binding: { thread_id: 'thr_work', work_id: 'work_created', research_id: 'research-created' },
    goal_revision: 1, snapshot_id: 'task_created', model_contexts: [], resource_refs: [] }
  const work = { work_id: 'work_created', goal: '新目标', goal_revision: 1, revision: 1, status: 'blocked',
    blocked_reason: 'execution_unavailable', task_context: context, messages: ['新目标'] }
  const snapshot = { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work', run: { run_id: 'run_work', state: 'open' },
    active_model_context: null, active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] as unknown[] }
  const commands: { target: { id: string } }[] = []
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (String(url).includes('/threads?')) return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (String(url).endsWith('/commands')) {
      const command = JSON.parse(String(init?.body)); commands.push(command); snapshot.works = [work]
      return response({ schema: 'capstone-command-receipt/1', thread_id: 'thr_work', command_id: command.command_id,
        idempotency_key: command.idempotency_key, status: 'accepted', target: { kind: 'work', id: 'work_created', expected_revision: 1 } })
    }
    return readFallback(url, snapshot) || response(snapshot)
  }))
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: '新目标' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByRole('textbox', { name: '补充任务资料' })
  expect(screen.getByRole('heading', { name: '历史任务会话' })).toBeTruthy()
  expect(screen.queryByRole('heading', { name: '新目标' })).toBeNull()
  expect(document.querySelectorAll('.capstone-chat-message.is-user')).toHaveLength(1)
  fireEvent.change(screen.getByRole('textbox', { name: '补充任务资料' }), { target: { value: '同一目标的补充' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await waitFor(() => expect(commands).toHaveLength(2))
  expect(commands[0].target.id).toBe('new')
  expect(commands[1].target.id).toBe('work_created')
})

it('does not insert a late professional history response into a different Thread', async () => {
  const base = { schema: 'capstone-thread-snapshot/2', run: { run_id: 'run_work', state: 'open' },
    active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] }
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  let complete!: (value: Response) => void
  vi.stubGlobal('fetch', vi.fn(async (url: string | URL) => {
    if (String(url).endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if (String(url).includes('/threads?')) return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if (String(url).includes('/thr_a/history?')) return new Promise<Response>(resolve => { complete = resolve })
    const read = readFallback(url, { last_event_seq: 0 }); if (read) return read
    if (String(url).endsWith('/thr_b')) return response({ ...base, thread_id: 'thr_b', active_model_context: null })
    return response({ ...base, thread_id: 'thr_a', selected_model_context_id: 'ctx_one', active_grid_page_id: 'page_one',
      active_model_context: { id: 'ctx_one', model_id: 'ieee39', model_revision: '1', implementation_family: 'pandapower', selection_revision: 'sel_one' } })
  }))
  render(<ThreadLiveEntry threadId="thr_a" mode="work" />)
  await waitFor(() => expect(complete).toBeTypeOf('function'))
  window.history.pushState({}, '', '/?workspace=enterprise&thread=thr_b'); fireEvent.popState(window)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: 'B的资料' } })
  await act(async () => { complete(response({ schema: 'capstone-thread-history/1', thread_id: 'thr_a', before_event_seq: 2,
    next_before_event_seq: 1, has_more: false, events: [{ event_id: 'evt_old', event_seq: 1, event_type: 'command_accepted',
      payload: { kind: 'send_auto', text: 'A的历史内容' }, event_version: 1, thread_id: 'thr_a', run_id: 'run_work',
      turn_id: 'turn_old', attempt_id: 'attempt_old', model_context_id: 'ctx_one', occurred_at: '2026-10-16T00:00:00Z', visibility: 'public' }] })) })
  await waitFor(() => expect((screen.getByRole('textbox', { name: '任务目标' }) as HTMLTextAreaElement).value).toBe('B的资料'))
  expect(screen.queryByText('A的历史内容')).toBeNull()
})

it('opens and restores a model-free work without preparing grid workers or submitting on refresh', async () => {
  document.title = 'Capstone · 电网分析工作台'
  const snapshot = { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: null,
    active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] }
  const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith('/thread-access')) return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'open' }))
    if (String(url).includes('/threads?')) return new Response(JSON.stringify({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null }), { headers: { 'Capstone-Thread-Version': '2' } })
    if (init?.method === 'POST') expect(JSON.parse(String(init.body))).toEqual({})
    return readFallback(url, snapshot) || new Response(JSON.stringify(snapshot), { headers: { 'Capstone-Thread-Version': '2' } })
  })
  vi.stubGlobal('fetch', fetcher)
  const first = render(<ThreadLiveEntry threadId="new" mode="work" />)
  expect(document.title).toBe('Capstone · 企业任务工作台')
  fireEvent.click(await screen.findByRole('button', { name: '新建任务会话' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '保存任务' }) as HTMLButtonElement).disabled).toBe(true))
  await screen.findByRole('button', { name: '刷新任务' })
  await screen.findByRole('textbox', { name: '任务目标' })
  expect(screen.getAllByTestId('assistant-ui-chat')).toHaveLength(1)
  expect(screen.queryByText('实时响应')).toBeNull()
  expect(screen.queryByText('围绕当前电网模型开始对话')).toBeNull()
  expect(fetcher.mock.calls.some(([url]) => String(url).includes('workbench-preparation'))).toBe(false)
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  first.unmount()
  expect(document.title).toBe('Capstone · 电网分析工作台')
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  await waitFor(() => expect(screen.getByRole('textbox', { name: '任务目标' })).toBeTruthy())
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  expect(screen.getByText(/保存不会自动启动执行/)).toBeTruthy()
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
    return readFallback(url, snapshot) || response(snapshot)
  }))
  const first = render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: '汇总资料中的结论' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByText('connection lost')
  first.unmount()
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  await screen.findByRole('button', { name: '重试保存' })
  expect(commands).toHaveLength(1)
  expect((screen.getByRole('textbox', { name: '任务目标' }) as HTMLTextAreaElement).disabled).toBe(true)
  await waitFor(() => expect((screen.getByRole('button', { name: '重试保存' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '重试保存' }))
  await screen.findByText('任务已保存。保存资料不会自动启动分析。')
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
    return readFallback(url, snapshot) || response(snapshot)
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
  await waitFor(() => expect((screen.getByRole('textbox', { name: '补充任务资料' }) as HTMLTextAreaElement).value).toBe('补充资料'))
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByRole('alert')
  expect(commands[0]?.target).toEqual({ kind: 'work', id: 'work_one', expected_revision: 1 })
  expect((screen.getByRole('textbox', { name: '补充任务资料' }) as HTMLTextAreaElement).disabled).toBe(false)
  expect((screen.getByRole('textbox', { name: '补充任务资料' }) as HTMLTextAreaElement).value).toBe('补充资料')
})
