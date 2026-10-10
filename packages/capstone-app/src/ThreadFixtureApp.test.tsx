import { afterEach, describe, expect, it } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { createFixtureTransport } from './threadProjectionStore'
import { threadUiFixture } from './threadUiFixtures'
import { historyContexts, historyFixture, historyWorkspace } from './threadHistory.test-support'
import { sampleDiagramView } from './networkFixture'

afterEach(cleanup)

function instructionViewsFixture(otherModel = false) {
  const fixture = structuredClone(threadUiFixture('idle-ieee39'))
  const snapshot = fixture.snapshot as { active_model_context: { id: string; model_revision: string }; last_event_seq: number }
  const diagram = structuredClone(sampleDiagramView.diagram)
  diagram.model = { ...diagram.model, id: 'ieee39', revision: snapshot.active_model_context.model_revision }
  const layer = { ...sampleDiagramView.layer, model_revision: diagram.model.revision }
  const reference = `result:sha256:${'a'.repeat(64)}`
  const events = [
    ['command_accepted', 'attempt_flow', { kind: 'send_auto', text: '运行潮流' }],
    ['network_diagram', 'attempt_flow', { diagram }],
    ['network_layer', 'attempt_flow', { ordinal: 1, layer: { ...layer, focus_ids: [], overlay: { metric: 'loading_percent', unit: '%', source_ref: reference, values: [{ id: 'line:1', value: 25 }] } } }],
    ['attempt_completed', 'attempt_flow', { answer: '全网潮流完成。', result_refs: [reference] }],
    ['command_accepted', 'attempt_rank', { kind: 'send_auto', text: '排序线路' }],
    ['network_diagram', 'attempt_rank', { diagram }],
    ['network_layer', 'attempt_rank', { ordinal: 1, layer: { ...layer, focus_ids: ['line:1'], overlay: { metric: 'loading_percent', unit: '%', source_ref: reference, values: [{ id: 'line:1', value: 42 }] } } }],
    ['attempt_completed', 'attempt_rank', { answer: '排序完成。', result_refs: [reference] }],
  ].map(([event_type, attempt_id, payload], index) => ({ event_id: `evt_graph_${index}`, event_seq: index + 1,
    event_type: String(event_type), attempt_id: String(attempt_id) as string | undefined, payload: payload as Record<string, unknown>, event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001',
    model_context_id: snapshot.active_model_context.id, occurred_at: '2026-10-05T00:00:00Z', visibility: 'public' }))
  snapshot.last_event_seq = events.length
  if (otherModel) {
    const previous = { ...snapshot.active_model_context, id: 'ctx_case57', model_id: 'case57', implementation_family: 'pandapower' }
    for (const entry of events.slice(0, 4)) {
      entry.model_context_id = previous.id
      if (entry.event_type === 'network_diagram') entry.payload = { diagram: { ...diagram, model: { ...diagram.model, id: 'case57' } } }
    }
    events.splice(4, 0, { ...events[0], event_id: 'evt_switch', event_type: 'model_context_activated', attempt_id: undefined,
      model_context_id: snapshot.active_model_context.id, payload: { previous_context: previous, previous_grid_page_id: 'page_case57',
        model_context: snapshot.active_model_context, active_grid_page_id: 'page_ieee39' } })
    events.forEach((entry, index) => { entry.event_seq = index + 1 })
    snapshot.last_event_seq = events.length
  }
  fixture.events = { schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 0, next_event_seq: events.length, has_more: false, events }
  return fixture
}

function focusFixture() {
  const fixture = historyFixture()
  const snapshot = fixture.snapshot as Record<string, unknown>
  snapshot.result_projections = [{
    schema: 'capstone-result-projection/1.0', result_id: 'result_focus',
    result_ref: `result:sha256:${'a'.repeat(64)}`, evidence_refs: [`evidence:sha256:${'b'.repeat(64)}`],
    thread_id: 'thr_history', run_id: 'run_history', turn_id: 'turn_result', attempt_id: 'attempt_result',
    model_context_id: historyContexts.active.id, model_id: 'ieee39', model_revision: historyContexts.active.model_revision,
    source: { capability_id: 'analysis.powerflow.ac.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
    status: 'completed', summary: [], overlay: null, element_refs: [{ element_kind: 'line', element_id: 'line:1' }],
    tables: [{ table_id: 'lines', title: '线路结果', columns: [{ column_id: 'line', label: '线路' }],
      rows: [{ row_id: 'line:1', cells: { line: '定位线路 1' }, element_ref: { element_kind: 'line', element_id: 'line:1' } }] }],
  }]
  const eventDocument = fixture.events as { events: Record<string, unknown>[]; next_event_seq: number }
  for (const [event_type, payload] of [
    ['command_accepted', { kind: 'send_professional', payload: { text: '查看线路' } }],
    ['attempt_completed', { answer: '线路结果已就绪。' }],
  ] as const) {
    const event_seq = eventDocument.events.length + 1
    eventDocument.events.push({ ...eventDocument.events.at(-1), event_id: `evt_${event_seq}`, event_seq, event_type, payload })
  }
  snapshot.last_event_seq = eventDocument.events.length
  eventDocument.next_event_seq = eventDocument.events.length
  return fixture
}

describe('ThreadFixtureApp', () => {
  it.each(['running', 'uncertain'] as const)('freezes configuration but preserves next-draft edits during %s', async state => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    if (state === 'running') Object.assign(fixture.snapshot as object, { current_attempt: { turn_id: 'turn_live', attempt_id: 'attempt_live', phase: 'running', target_model_context_id: 'ctx_ieee39_7' } })
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport, sendCommand: async command => { commands.push(command); throw new Error('receipt unavailable') } })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    if (state === 'uncertain') {
      fireEvent.change(input, { target: { value: 'accepted candidate' } })
      fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
      await screen.findByText(/操作提交结果尚未确认/)
    }
    expect(input.disabled).toBe(false)
    for (const name of ['运行模式', '选择技能', '本轮上下文']) expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    for (const checkbox of screen.getAllByRole('checkbox')) expect((checkbox as HTMLInputElement).disabled).toBe(true)
    fireEvent.change(input, { target: { value: 'next draft preserved' } })
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })
    expect(input.value).toBe('next draft preserved')
    expect(commands).toHaveLength(state === 'running' ? 0 : 1)
  })
  it.each([['send', 'click'], ['runtime', 'click'], ['send', 'Enter'], ['runtime', 'Enter']] as const)('admits only one operation for same-tick %s-first %s actions and keeps editing available', async (first, trigger) => {
    const transport = createFixtureTransport(structuredClone(threadUiFixture('idle-ieee39')))
    const commands: ThreadCommand[] = []
    let release!: () => void
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport, sendCommand: command => {
      commands.push(command)
      return new Promise(resolve => { release = () => resolve({ schema: 'capstone-command-receipt/1', command_id: command.command_id,
        idempotency_key: command.idempotency_key, thread_id: command.thread_id, status: 'rejected', rejection: 'stale_event_seq' }) })
    } })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'keep draft' } })
    fireEvent.click(screen.getByRole('button', { name: '运行模式' }))
    const mode = screen.getByRole('menuitemradio', { name: 'Pi' })
    const send = screen.getByRole('button', { name: '发送指令' })
    const submit = () => trigger === 'click' ? send.click() : fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })
    act(() => { if (first === 'send') { submit(); mode.click() } else { mode.click(); submit() } })
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0].kind).toBe(first === 'send' ? 'send_auto' : 'switch_runtime')
    expect(input.disabled).toBe(false)
    expect((screen.getByRole('button', { name: '选择技能' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(input, { target: { value: 'next draft' } })
    expect(input.value).toBe('next draft')
    release()
    await waitFor(() => expect((screen.getByRole('button', { name: '运行模式' }) as HTMLButtonElement).disabled).toBe(false))
  })

  it.each(['capstone', 'pi_reference'])('rebuilds typed context input and recovers the original draft after an ordered model change in %s', async mode => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    const snapshot = fixture.snapshot as Record<string, any>
    snapshot.runtime_mode = mode
    const original = structuredClone(snapshot.active_model_context)
    let transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    let catalogReads = 0
    let loseReceipt = true
    const client = new CapstoneThreadClient({
      getSnapshot: id => transport.getSnapshot(id), getCatalog: id => transport.getCatalog!(id),
      readEvents: (id, cursor) => transport.readEvents(id, cursor),
      getModels: async () => ({ schema: 'capstone-thread-model-workspace/1', thread_id: 'thr_demo_39', run_id: 'run_001', event_seq: snapshot.last_event_seq,
        current_entry_id: 'mdl_current', blocked_reason: null, models: [{ entry_id: 'mdl_current', ...snapshot.active_model_context,
          authority_model_ref: null, display_name: snapshot.active_model_context.model_id, diagram_provider_id: null, last_active_seq: 0 }].map(({ id, selection_revision, ...entry }) => entry) }),
      getInputCatalog: async () => { catalogReads++; return { schema: 'capstone-thread-input-catalog/1', revision: 'catalog',
        context_id: snapshot.active_model_context.id, selection_revision: snapshot.active_model_context.selection_revision,
        objects: [original, snapshot.active_model_context].filter((value, index, values) => values.findIndex(item => item.id === value.id) === index)
          .map(value => ({ object_id: value.id, model_id: value.model_id, model_revision: value.model_revision, implementation_family: value.implementation_family })),
        materials: [], operations: [], resource_profiles: {} } },
      sendCommand: async command => {
        commands.push(command)
        if (command.kind === 'open_model') {
          snapshot.active_model_context = { ...original, id: 'ctx_pypsa', model_id: 'pypsa39', implementation_family: 'pypsa' }
          snapshot.last_event_seq = 1; snapshot.active_grid_page_id = 'page_pypsa39'
          fixture.events = { schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 0, next_event_seq: 1, has_more: false,
            events: [{ event_id: 'evt_model', event_seq: 1, event_type: 'model_context_activated', event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001',
              occurred_at: '2026-10-09T00:00:00Z', visibility: 'public', payload: { previous_context: original, model_context: snapshot.active_model_context, active_grid_page_id: 'page_pypsa39' } }] }
          transport = createFixtureTransport(fixture)
          return { schema: 'capstone-command-receipt/1', command_id: command.command_id, idempotency_key: command.idempotency_key, thread_id: command.thread_id, status: 'accepted', accepted_event_seq: 1 }
        }
        const receipt = await transport.sendCommand(command)
        if (loseReceipt) { loseReceipt = false; throw new Error('accepted receipt lost') }
        return receipt
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.click(screen.getByRole('button', { name: '本轮上下文' }))
    fireEvent.click(await screen.findByRole('button', { name: '包含' }))
    await act(async () => {})
    fireEvent.keyDown(input, { key: 'Escape' })
    fireEvent.change(input, { target: { value: '打开 pypsa39，然后分析电压' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands.map(command => command.kind)).toEqual(['open_model', 'send_auto'])
    expect(commands[1].payload).toMatchObject({ text: '分析电压', input: { kind: 'text', text: '分析电压' }, context_selection: { include_refs: [original.id], exclude_refs: [] } })
    expect(catalogReads).toBeGreaterThan(1)
    await screen.findByText(/操作提交结果尚未确认/)
    await waitFor(() => expect((input as HTMLTextAreaElement).value).toBe('打开 pypsa39，然后分析电压'))
    fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
    await waitFor(() => expect(commands).toHaveLength(3))
    expect(commands[2]).toEqual(commands[1])
    await waitFor(() => expect((input as HTMLTextAreaElement).value).toBe(''))
  })
  it.each(['capstone', 'pi_reference'])('retries a direct Pi attempt with disabled domain tools in %s mode', async (mode) => {
    const fixture = instructionViewsFixture()
    const document = fixture.events as { events: Record<string, unknown>[]; next_event_seq: number }
    document.events = [
      { ...document.events[0], event_seq: 1, payload: { kind: 'send_auto', runtime_mode: 'pi_reference', payload: { text: 'Explain a poem' } } },
      { ...document.events[0], event_id: 'evt_failed', event_seq: 2, event_type: 'attempt_failed', payload: { diagnostic_code: 'execution_failed' } },
    ]
    document.next_event_seq = 2
    Object.assign(fixture.snapshot as object, { last_event_seq: 2, runtime_mode: mode })
    Object.assign((fixture.snapshot as { active_model_context: object }).active_model_context,
      { enabled_profiles: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [{ profile_id: 'pandapower-static-analysis', profile_version: '1.0.1' }] } })
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp disabledToolIds={['pandapower-static-analysis']} client={new CapstoneThreadClient({ ...transport,
      sendCommand: async command => { commands.push(command); return transport.sendCommand(command) },
    })} threadId="thr_demo_39" />)
    fireEvent.click(await screen.findByRole('button', { name: '重试本次指令' }))
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0]).toMatchObject({ kind: 'retry_new_attempt', payload: { attempt_id: 'attempt_flow' } })
  })
  it('holds the runtime selector during submission and retains draft after rejection', async () => {
    const transport = createFixtureTransport(structuredClone(threadUiFixture('idle-ieee39')))
    let resolve!: (value: unknown) => void
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport,
      sendCommand: async (command) => new Promise(done => { resolve = () => done({ schema: 'capstone-command-receipt/1', command_id: command.command_id,
        idempotency_key: command.idempotency_key, thread_id: command.thread_id, run_id: command.run_id, status: 'rejected', rejection: 'attempt_in_progress' }) }),
    })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'keep this draft' } })
    const selector = screen.getByRole('button', { name: '运行模式' }) as HTMLButtonElement
    fireEvent.click(selector)
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Pi' }))
    await waitFor(() => expect(selector.disabled).toBe(true))
    resolve(undefined)
    await waitFor(() => expect(selector.disabled).toBe(false))
    expect(selector.textContent).toBe('Capstone')
    expect(input.value).toBe('keep this draft')
  })
  it('shows why a registered Case cannot start in direct Pi mode', async () => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    ;(fixture.snapshot as Record<string, unknown>).runtime_mode = 'pi_reference'
    const transport = createFixtureTransport(fixture)
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport,
      getCatalog: async () => ({ schema: 'capstone-thread-catalog/1', models: [], profiles: [],
        cases: [{ case_id: 'case_demo', case_version: '1', title: 'Demo', summary: 'Registered', model_ids: ['ieee39'], step_count: 1 }] }),
    })} threadId="thr_demo_39" />)
    expect(await screen.findByText('请先切换到 Capstone')).toBeTruthy()
    expect((screen.getByRole('button', { name: '开始案例' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('switches runtime without losing draft or model and sends direct tasks unchanged', async () => {
    const transport = createFixtureTransport(structuredClone(threadUiFixture('idle-ieee39')))
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport,
      sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) },
    })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '打开 case57 电网模型' } })
    const selector = screen.getByRole('button', { name: '运行模式' })
    fireEvent.click(selector)
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Pi' }))
    await waitFor(() => expect(selector.textContent).toBe('Pi'))
    await screen.findByText('已切换至 Pi 模式。')
    await waitFor(() => expect((selector as HTMLButtonElement).disabled).toBe(false))
    expect(input.value).toBe('打开 case57 电网模型')
    expect(document.querySelector('.thread-model-short')?.textContent).toContain('ieee39')
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands.map(command => command.kind)).toEqual(['switch_runtime', 'send_auto'])
    expect(commands[1].payload).toEqual({ text: '打开 case57 电网模型', input: { kind: 'text', text: '打开 case57 电网模型' } })
  })
  it('lists a returned model once while retaining the other model history', async () => {
    // Fresh Thread: IEEE-39 -> another model -> IEEE-39, unchanged model revision.
    const fixture = historyFixture()
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...createFixtureTransport(fixture),
      getModels: async () => historyWorkspace((fixture.snapshot as { last_event_seq: number }).last_event_seq),
    })} threadId="thr_history" />)
    fireEvent.click(await screen.findByRole('button', { name: '当前模型：IEEE-39' }))
    expect(screen.getAllByRole('button', { name: /^设为当前模型：IEEE-39/ })).toHaveLength(1)
    expect(screen.getByRole('button', { name: /^设为当前模型：Regional Six Bus/ })).toBeTruthy()
    expect(screen.queryByText(/^模型历史/)).toBeNull()
    expect(document.querySelector('.thread-page-tabs')).toBeNull()
  })

  it('does not restore backend defaults when a saved preference has no available catalog', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp disabledToolIds={['pandapower-static-analysis']} client={new CapstoneThreadClient({ ...transport,
      getCatalog: async () => ({ schema: 'capstone-thread-catalog/1', models: [], profiles: [] }),
      sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) },
    })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '计算潮流' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await screen.findByText('工具目录暂不可用，请重新连接后重试。')
    expect(commands).toEqual([])
    expect(input.value).toBe('计算潮流')
  })

  it('keeps global choices and submits empty selection for backend capability gating', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport, sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) } })} threadId="thr_demo_39" />)
    await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'pandapower 静态分析' }))
    fireEvent.click(screen.getByRole('button', { name: '保存工具选择' }))
    expect(commands).toEqual([])
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '计算潮流' } })
    await waitFor(() => expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await screen.findByText('Fixture 已接收自动指令：计算潮流')
    expect(commands).toHaveLength(1)
    expect(commands[0].payload.enabled_profiles).toEqual([])
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('checkbox', { name: 'pandapower 静态分析' }) as HTMLInputElement).checked).toBe(false)
  })

  it('submits the compatible enabled subset on each task without exposing another family', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport, sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) } })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.change(input, { target: { value: '计算潮流' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0].payload.enabled_profiles).toEqual([{ profile_id: 'pandapower-static-analysis', profile_version: '1.0.1' }])
  })

  it('uses the enabled target tools for a model-opening turn when the current tools are disabled', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp disabledToolIds={['pandapower-static-analysis']} client={new CapstoneThreadClient({ ...transport,
      sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) },
    })} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.change(input, { target: { value: '打开 pypsa39 电网模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands[0]).toMatchObject({ kind: 'switch_model', payload: { model_id: 'pypsa39' } })
    expect(commands[1].payload.enabled_profiles).toEqual([{ profile_id: 'pypsa-business-cases', profile_version: '1.0.0' }])
    await waitFor(() => expect((screen.getByRole('button', { name: '对话设置' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect((screen.getByRole('checkbox', { name: 'pandapower 静态分析' }) as HTMLInputElement).checked).toBe(false)
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).checked).toBe(true)
  })

  it('does not create a second Turn when the first command committed before its receipt was lost', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport,
      sendCommand: async (command) => {
        commands.push(command)
        const receipt = await transport.sendCommand(command)
        if (commands.length === 1) throw new Error('committed receipt lost')
        return receipt
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.change(input, { target: { value: '读取母线' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await screen.findByText(/操作提交结果尚未确认/)
    expect(screen.queryByText(/committed receipt lost/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
    await screen.findByText('Fixture 已接收自动指令：读取母线')
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands[1]).toEqual(commands[0])
    expect(screen.getAllByText('Fixture 已接收自动指令：读取母线')).toHaveLength(1)
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('')
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it.each(['accepted', 'rejected', 'still unknown'])('preserves a lost-receipt draft and checks the original command: %s', async (outcome) => {
    const fixture = threadUiFixture('idle-ieee39')
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport,
      sendCommand: async (command) => {
        commands.push(command)
        if (commands.length === 1 || outcome === 'still unknown') throw new Error('receipt connection lost')
        return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id,
          command_id: command.command_id, idempotency_key: command.idempotency_key,
          status: outcome, ...(outcome === 'rejected' ? { rejection: 'stale_event_seq' } : {}) }
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    const text = '读取当前模型的母线'
    fireEvent.change(input, { target: { value: text } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await screen.findByText(/操作提交结果尚未确认/)
    await waitFor(() => expect((input as HTMLTextAreaElement).value).toBe(text))
    fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands[1]).toEqual(commands[0])
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value)
      .toBe(outcome === 'accepted' ? '' : text))
    if (outcome === 'rejected') expect(await screen.findByText(/stale_event_seq/)).toBeTruthy()
    if (outcome !== 'still unknown') expect(screen.queryByText(/操作提交结果尚未确认/)).toBeNull()
  })

  it('restores an unsent draft after a page remount and keeps it scoped to its Thread', async () => {
    const client = new CapstoneThreadClient(createFixtureTransport(threadUiFixture('idle-ieee39')))
    const first = render(<ThreadFixtureApp client={client} threadId="thr_demo_39" storageKey="test-thread-draft" />)
    fireEvent.change(await screen.findByRole('textbox', { name: 'Thread 指令' }), { target: { value: '刷新后还应保留' } })
    expect(sessionStorage.getItem('test-thread-draft.draft')).toBe('刷新后还应保留')
    first.unmount()
    expect(sessionStorage.getItem('test-thread-draft.draft')).toBe('刷新后还应保留')
    const second = render(<ThreadFixtureApp client={client} threadId="thr_demo_39" storageKey="test-thread-draft" />)
    await screen.findByRole('textbox', { name: 'Thread 指令' })
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('刷新后还应保留'))
    second.unmount()
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" storageKey="another-thread" />)
    expect((await screen.findByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('')
    sessionStorage.removeItem('test-thread-draft.draft')
  })

  it('automatically reconnects a lost event stream without a click', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    let attempts = 0
    let fail!: () => void
    const client = new CapstoneThreadClient({ ...transport,
      streamEvents: async function* () {
        attempts += 1
        if (attempts === 1) {
          await new Promise<void>((resolve) => { fail = resolve })
          throw new Error('deploy disconnect')
        }
        await new Promise<void>(() => {})
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    fireEvent.change(await screen.findByRole('textbox', { name: 'Thread 指令' }), { target: { value: '重连草稿' } })
    fail()
    await waitFor(() => expect(attempts).toBe(2), { timeout: 2500 })
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('重连草稿')
  })

  it('preserves an unsent draft across an event-stream reconnect', async () => {
    let failStream!: () => void
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const client = new CapstoneThreadClient({ ...transport,
      streamEvents: async function* () {
        await new Promise<void>((resolve) => { failStream = resolve })
        throw new Error('stream connection lost')
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.change(input, { target: { value: '尚未发送的下一条指令' } })
    failStream()
    await screen.findByText(/连接暂时中断/)
    fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
    await waitFor(() => expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(false))
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('尚未发送的下一条指令')
  })

  it('keeps an offline reconnect recoverable without losing the draft', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    let loads = 0
    let failStream!: () => void
    const client = new CapstoneThreadClient({ ...transport,
      getSnapshot: async (id) => {
        if (++loads === 2) throw new Error('snapshot offline')
        return transport.getSnapshot(id)
      },
      streamEvents: async function* () {
        await new Promise<void>((resolve) => { failStream = resolve })
        throw new Error('stream offline')
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.change(input, { target: { value: '持续保留草稿' } })
    failStream()
    await screen.findByText(/连接暂时中断/)
    fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
    await waitFor(() => expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true))
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('持续保留草稿')
    fireEvent.click(screen.getByRole('button', { name: '重新连接' }))
    await waitFor(() => expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(false))
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('持续保留草稿')
  })
  it('reruns a completed instruction as a new command without changing its old answer', async () => {
    const fixture = instructionViewsFixture()
    const document = fixture.events as { events: Record<string, unknown>[]; next_event_seq: number }
    document.events = [
      { ...document.events[0], event_seq: 1, event_type: 'command_accepted', payload: { kind: 'send_auto', payload: { text: '读取当前模型' } } },
      { ...document.events.find(event => event.event_type === 'attempt_completed'), event_seq: 2, payload: { answer: '原回答已完成。' } },
    ]
    document.next_event_seq = 2
    ;(fixture.snapshot as { last_event_seq: number }).last_event_seq = 2
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const retry = await screen.findByRole('button', { name: '重试本次指令' })
    expect((retry as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(retry)
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0]).toMatchObject({ kind: 'send_auto', payload: { text: '读取当前模型' }, expected_event_seq: 2 })
    expect(await screen.findByText('Fixture 已接收自动指令：读取当前模型')).toBeTruthy()
    expect(screen.getByText('原回答已完成。')).toBeTruthy()
  })
  it('puts the model directory beside Composer settings and preserves its draft', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)
    const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
    expect(screen.getByRole('button', { name: '回到模型视角' })).toBeTruthy()
    fireEvent.change(input, { target: { value: '保留此草稿' } })
    const opener = screen.getByRole('button', { name: '模型目录' })
    expect(opener.closest('.capstone-composer-toolbar')).toBeTruthy()
    expect(opener.closest('.thread-model-pane')).toBeNull()
    fireEvent.click(opener)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'pypsa' } })
    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Enter' })
    expect((input as HTMLTextAreaElement).value).toBe('保留此草稿')
    expect(screen.queryByText('Fixture 已接收自动指令：保留此草稿')).toBeNull()
  })
  it.each([false, true])('resets the viewed task camera and locates its own instruction, other model: %s', async (otherModel) => {
    const fixture = instructionViewsFixture(otherModel)
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const actions = await screen.findAllByRole('button', { name: '查看此指令电网图' })
    expect(document.querySelector('svg title')?.textContent).toContain('42.0')
    fireEvent.click(actions[0])
    expect(screen.getAllByRole('button', { name: '查看此指令电网图' })[0].getAttribute('aria-pressed')).toBe('true')
    expect(await screen.findByText('正在查看此回答对应的电网图')).toBeTruthy()
    expect(document.querySelector('svg title')?.textContent).toContain('25.0')
    expect(document.querySelectorAll('.network-branch-label')).toHaveLength(0)
    const canvas = screen.getByRole('img', { name: '电网拓扑' })
    const initialCamera = canvas.getAttribute('viewBox')
    const currentModel = document.querySelector('.thread-model-short')?.textContent
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    fireEvent.keyDown(canvas, { key: 'ArrowRight' })
    expect(canvas.getAttribute('viewBox')).not.toBe(initialCamera)
    fireEvent.click(within(screen.getByLabelText('电网图操作')).getByRole('button', { name: '回到任务' }))
    await waitFor(() => expect(screen.getAllByLabelText('用户指令')[0].classList.contains('is-located-instruction')).toBe(true))
    expect(document.querySelector('svg title')?.textContent).toContain('25.0')
    expect(document.querySelectorAll('.network-branch-label')).toHaveLength(0)
    expect(canvas.getAttribute('viewBox')).toBe(initialCamera)
    expect(document.querySelector('.thread-model-short')?.textContent).toBe(currentModel)
    expect(commands).toEqual([])
    fireEvent.click(screen.getByRole('button', { name: '回到当前任务' }))
    await waitFor(() => expect(document.querySelector('svg title')?.textContent).toContain('42.0'))
    expect(document.querySelectorAll('.network-branch-label')).toHaveLength(1)
    expect(commands).toEqual([])
    expect(screen.getAllByLabelText('用户指令')[1].classList.contains('is-located-instruction')).toBe(true)
  })
  it.each(['model change', 'profile change', 'active attempt', 'repeated rejection'])('retains a preset draft after stale recovery with %s', async (condition) => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    const transport = createFixtureTransport(fixture)
    const context = (fixture.snapshot as { active_model_context: Record<string, unknown> }).active_model_context
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport,
      readEvents: async (threadId, after) => {
        if (!commands.length || after >= 1) return { schema: 'capstone-thread-events/1', thread_id: threadId, after_event_seq: after, next_event_seq: after, has_more: false, events: [] }
        const change = condition === 'model change' ? {
          event_type: 'model_context_activated', payload: { model_context: { ...context, id: 'ctx_other', model_id: 'pypsa39', implementation_family: 'pypsa' }, active_grid_page_id: 'page_pypsa39' },
        } : condition === 'profile change' ? {
          event_type: 'selection_activated', selection_revision: 'sel_3', payload: { selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] } },
        } : condition === 'active attempt' ? {
          event_type: 'attempt_started', turn_id: 'turn_other', attempt_id: 'attempt_other', model_context_id: context.id, payload: {},
        } : { event_type: 'runtime_event', payload: {} }
        return { schema: 'capstone-thread-events/1', thread_id: threadId, after_event_seq: after, next_event_seq: 1, has_more: false,
          events: [{ event_id: 'evt_background', event_seq: 1, event_version: 1, thread_id: threadId, run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', ...change }],
        }
      },
      sendCommand: async (command) => {
        commands.push(command)
        return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id, command_id: command.command_id, idempotency_key: command.idempotency_key, status: 'rejected', rejection: 'stale_event_seq' }
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const prompt = '有哪些 PyPSA 的电网模型？'
    fireEvent.click(await screen.findByRole('button', { name: prompt }))
    await screen.findByText(/stale_event_seq/)
    expect(commands).toHaveLength(condition === 'repeated rejection' ? 2 : 1)
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe(prompt))
  })

  it('executes a preset directly and recovers one stale cursor without sending twice', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    let advanced = false
    const client = new CapstoneThreadClient({ ...transport,
      readEvents: async (threadId, after) => advanced && after < 1 ? {
        schema: 'capstone-thread-events/1', thread_id: threadId, after_event_seq: after,
        next_event_seq: 1, has_more: false, events: [{
          event_id: 'evt_background', event_seq: 1, event_type: 'runtime_event', event_version: 1,
          thread_id: threadId, run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z',
          visibility: 'diagnostic', payload: {},
        }],
      } : { schema: 'capstone-thread-events/1', thread_id: threadId, after_event_seq: after, next_event_seq: after, has_more: false, events: [] },
      sendCommand: async (command) => {
        commands.push(command)
        advanced = true
        return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id,
          command_id: command.command_id, idempotency_key: command.idempotency_key,
          status: command.expected_event_seq === 1 ? 'accepted' : 'rejected',
          ...(command.expected_event_seq === 1 ? {} : { rejection: 'stale_event_seq' }),
        }
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    const prompt = '有哪些 PyPSA 的电网模型？'
    fireEvent.click(await screen.findByRole('button', { name: prompt }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands.map((item) => item.expected_event_seq)).toEqual([0, 1])
    expect(commands.every((item) => item.kind === 'send_auto' && item.payload.text === prompt)).toBe(true)
    expect(commands[1].command_id).not.toBe(commands[0].command_id)
    expect(commands[1].idempotency_key).not.toBe(commands[0].idempotency_key)
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe(''))
    expect(screen.queryByText(/stale_event_seq/)).toBeNull()
  })

  it('activates a matching pending reopen instead of discarding a recovered draft', async () => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    const snapshot = fixture.snapshot as Record<string, unknown>
    snapshot.pending_model_switch = { command_id: 'cmd_reopen', model_id: 'ieee39', model_revision: '7', implementation_family: 'pandapower', reason: 'explicit_reopen', selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] } }
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport, sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) } })} threadId="thr_demo_39" />)
    await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '重新打开 ieee39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands.map((command) => command.kind)).toEqual(['send_auto']))
  })

  it('keeps the model selector disabled while an Attempt is active and permits cancellation', async () => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    ;(fixture.snapshot as Record<string, unknown>).current_attempt = { turn_id: 'turn_active', attempt_id: 'attempt_active', phase: 'running', target_model_context_id: 'ctx_ieee39_7' }
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(fixture))} threadId="thr_demo_39" />)
    await screen.findByRole('textbox', { name: 'Thread 指令' })
    fireEvent.click(screen.getByRole('button', { name: '模型目录' }))
    fireEvent.change(screen.getByRole('listbox', { name: '目标电网模型' }), { target: { value: 'pypsa39' } })
    expect((screen.getByRole('listbox', { name: '目标电网模型' }) as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '运行模式' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '停止生成' }) as HTMLButtonElement).disabled).toBe(false)
  })
  it('uses the selected earlier result overlay when focusing its current-context row', async () => {
    const fixture = focusFixture()
    const snapshot = fixture.snapshot as { result_projections: Record<string, unknown>[] }
    const original = snapshot.result_projections[0]
    original.overlay = { metric: 'loading_percent', unit: '%', source_ref: original.result_ref, values: [{ element_id: 'line:1', value: 25 }] }
    snapshot.result_projections.push({ ...original, result_id: 'result_later', result_ref: `result:sha256:${'d'.repeat(64)}`, tables: [], overlay: { metric: 'loading_percent', unit: '%', source_ref: `result:sha256:${'d'.repeat(64)}`, values: [{ element_id: 'line:1', value: 90 }] } })
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(fixture))} threadId="thr_history" />)
    await screen.findByRole('region', { name: '电网模型区' })
    expect(document.querySelector('svg title')?.textContent).toContain('90.0')
    fireEvent.click(screen.getByRole('button', { name: '查看分析结果' }))
    fireEvent.click(screen.getByRole('button', { name: '定位线路 1' }))
    expect(await screen.findByText('已定位到 line:1')).toBeTruthy()
    expect(document.querySelector('svg title')?.textContent).toContain('25.0')
  })
  it('selects a registered suffixed model and sends the original instruction with the caught-up cursor', async () => {
    const fixture = threadUiFixture('idle-ieee39')
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    let switched = false
    const client = new CapstoneThreadClient({ ...transport,
      getCatalog: async () => ({ schema: 'capstone-thread-catalog/1', profiles: [], models: [{ model_id: 'case24_ieee_rts', authority_model_ref: 'gridctl:case24_ieee_rts', display_name: 'RTS-24', diagram_provider_id: 'pandapower', implementation_family: 'pandapower' }] }),
      readEvents: async (threadId, after) => switched ? {
        schema: 'capstone-thread-events/1', thread_id: threadId, after_event_seq: after,
        next_event_seq: 2, has_more: false, events: [
          { event_id: 'evt_switch', event_seq: 1, event_type: 'command_accepted', event_version: 1, thread_id: threadId, run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload: { kind: 'switch_model' } },
          { event_id: 'evt_pending', event_seq: 2, event_type: 'model_context_change_pending', event_version: 1, thread_id: threadId, run_id: 'run_001', occurred_at: '2026-10-05T00:00:00Z', visibility: 'public', payload: { command_id: commands[0].command_id, model_id: 'case24_ieee_rts', model_revision: '1', implementation_family: 'pandapower', selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] } } },
        ].filter((event) => event.event_seq > after),
      } : transport.readEvents(threadId, after),
      sendCommand: async (command) => {
        commands.push(command)
        switched = true
        return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id, command_id: command.command_id, idempotency_key: command.idempotency_key, status: 'accepted', accepted_event_seq: 1 }
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    await screen.findByRole('textbox', { name: 'Thread 指令' })
    const request = '打开 case24_ieee_rts 电网模型'
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands[0]).toMatchObject({ kind: 'switch_model', payload: { model_id: 'case24_ieee_rts' }, expected_event_seq: 0 })
    expect(commands[1]).toMatchObject({ kind: 'send_auto', payload: { text: request }, expected_event_seq: 2 })
    expect(commands[1].command_id).not.toBe(commands[0].command_id)
  })

  it.each(['ambiguous', 'unavailable', 'rejected', 'transport'])('keeps the composer draft after a %s model request', async (failure) => {
    const fixture = threadUiFixture('idle-ieee39')
    const transport = createFixtureTransport(fixture)
    const model = { model_id: 'pypsa-example/two-bus', authority_model_ref: 'pypsa:two-bus', display_name: 'Two Bus', diagram_provider_id: 'pypsa', implementation_family: 'pypsa', available: failure !== 'unavailable' }
    const client = new CapstoneThreadClient({ ...transport,
      getCatalog: async () => ({ schema: 'capstone-thread-catalog/1', profiles: [], models: failure === 'ambiguous' ? [model, { ...model, model_id: 'other/two-bus' }] : [model] }),
      sendCommand: async (command) => {
        if (failure === 'transport') throw new Error('connection lost')
        return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id, command_id: command.command_id, idempotency_key: command.idempotency_key, status: 'rejected', rejection: 'stale_event_seq' }
      },
    })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    await screen.findByRole('textbox', { name: 'Thread 指令' })
    const request = '打开 two-bus'
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe(request))
  })
  it.each([
    ['foreign model', { model_id: 'regional-six-bus' }, '该结果属于历史模型修订，已保持只读，未改变当前电网图'],
    ['foreign revision', { model_revision: historyContexts.historical.model_revision }, '该结果属于历史模型修订，已保持只读，未改变当前电网图'],
    ['prior Context of the same model revision', { model_context_id: historyContexts.initial.id }, '该结果属于历史模型修订，已保持只读，未改变当前电网图'],
  ])('declines focus from a %s', async (_name, changes, notice) => {
    const fixture = focusFixture()
    const snapshot = fixture.snapshot as { result_projections: Record<string, unknown>[] }
    Object.assign(snapshot.result_projections[0], changes)
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(fixture))} threadId="thr_history" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '查看分析结果' }))
    fireEvent.click(screen.getByRole('button', { name: '定位线路 1' }))
    expect(await screen.findByText(String(notice))).toBeTruthy()
    expect(document.querySelector('.network-branch-label')).toBeNull()
  })

  it('declines an unknown result element without applying focus', async () => {
    const fixture = focusFixture()
    const snapshot = fixture.snapshot as { result_projections: Array<{ element_refs: unknown[]; tables: Array<{ rows: Array<{ element_ref: unknown }> }> }> }
    const reference = { element_kind: 'line', element_id: 'line:unknown' }
    snapshot.result_projections[0].element_refs = [reference]
    snapshot.result_projections[0].tables[0].rows[0].element_ref = reference
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(fixture))} threadId="thr_history" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '查看分析结果' }))
    fireEvent.click(screen.getByRole('button', { name: '定位线路 1' }))
    expect(await screen.findByText('当前电网图中没有这个元件，无法定位')).toBeTruthy()
    expect(document.querySelector('.network-branch-label')).toBeNull()
  })

  it('keeps new Attempt retry disabled while viewing history', async () => {
    const fixture = historyFixture()
    Object.assign(fixture.snapshot as Record<string, unknown>, { current_attempt: {
      turn_id: 'turn_result', attempt_id: 'attempt_result', phase: 'interrupted', target_model_context_id: historyContexts.active.id,
    } })
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(fixture))} threadId="thr_history" />)
    fireEvent.click(await screen.findByRole('button', { name: /Regional Six Bus.*历史/ }))
    expect((screen.getByRole('button', { name: '重试新 Attempt' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('keeps case retry read-only while permitting live case cancellation in history', async () => {
    const fixture = historyFixture()
    Object.assign(fixture.snapshot as Record<string, unknown>, { application_state: { case_execution: {
      display_name: '测试案例', status: 'blocked', completed_steps: 0, total_steps: 1, current_step: 1,
      steps: [{ ordinal: 1, title: '线路检查', status: 'interrupted', duration_ms: null,
        details: { case_execution_id: 'case_execution_live', failed_attempt_id: 'attempt_result' } }],
      actions: [{ action_id: 'retry_case_step', label: '重试此步骤', enabled: true }, { action_id: 'cancel_case', label: '停止案例', enabled: true }],
      disabled_reasons: ['步骤已中断'],
    } } })
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    render(<ThreadFixtureApp client={client} threadId="thr_history" />)
    fireEvent.click(await screen.findByRole('button', { name: /Regional Six Bus.*历史/ }))
    expect((screen.getByRole('button', { name: '重试此步骤' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '停止案例' }))
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0]).toMatchObject({ kind: 'cancel_case_execution', payload: { case_execution_id: 'case_execution_live' } })
    expect(screen.getByText('ctx_regional')).toBeTruthy()
  })

  it('submits live Attempt cancellation while the selected page stays historical', async () => {
    const fixture = historyFixture()
    Object.assign(fixture.snapshot as Record<string, unknown>, { current_attempt: {
      turn_id: 'turn_result', attempt_id: 'attempt_result', phase: 'running', target_model_context_id: historyContexts.active.id,
    } })
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    render(<ThreadFixtureApp client={client} threadId="thr_history" />)
    fireEvent.click(await screen.findByRole('button', { name: /Regional Six Bus.*历史/ }))
    fireEvent.click(screen.getByRole('button', { name: '停止生成' }))
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0]).toMatchObject({ kind: 'cancel_live_attempt', payload: { attempt_id: 'attempt_result' } })
    expect(screen.getByText('ctx_regional')).toBeTruthy()
  })

  it('declines result focus while a historical page is selected and allows it after return to current', async () => {
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(focusFixture()))} threadId="thr_history" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: /Regional Six Bus.*历史/ }))
    fireEvent.click(screen.getByRole('button', { name: '查看分析结果' }))
    fireEvent.click(screen.getByRole('button', { name: '定位线路 1' }))
    expect(await screen.findByText('历史页为只读视图，请返回当前模型后定位')).toBeTruthy()
    expect(screen.queryByText('已定位到 line:1')).toBeNull()
    expect(document.querySelector('.network-branch-label')).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: '返回当前模型' })[0])
    expect(document.querySelector('.network-branch-label')).toBeNull()
    // Changing the viewed page preserves the open result panel.
    expect(screen.getByRole('button', { name: '查看分析结果' }).getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: '定位线路 1' }))
    expect(await screen.findByText('已定位到 line:1')).toBeTruthy()
    expect(document.querySelector('.network-branch-label')?.textContent).toBe('line 1')
  })
  it('discovers typed history pages and displays their own read-only context without sending commands', async () => {
    const fixture = historyFixture()
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    render(<ThreadFixtureApp client={client} threadId="thr_history" />)
    await screen.findByRole('button', { name: '模型目录' })
    fireEvent.click(screen.getByText(/^模型历史/))
    const history = await screen.findByRole('button', { name: /Regional Six Bus.*历史/ })
    fireEvent.click(history)

    expect(await screen.findByText('历史页 · 只读视图')).toBeTruthy()
    fireEvent.click(screen.getByText('电网视图详情 · 历史只读'))
    fireEvent.click(screen.getByRole('button', { name: '模型目录' }))
    expect(screen.getByText('ctx_regional')).toBeTruthy()
    expect(screen.getByText('sel_1')).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect((screen.getByRole('listbox', { name: '目标电网模型' }) as HTMLSelectElement).disabled).toBe(true)
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).disabled).toBe(false)
    expect(document.querySelector('.thread-model-short')?.textContent).toBe('ieee39 · pandapower')
    expect(commands).toEqual([])
    fireEvent.click(screen.getAllByRole('button', { name: '返回当前模型' })[0])
    expect(await screen.findByText('ctx_ieee_new')).toBeTruthy()
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).disabled).toBe(false)
    expect(commands).toEqual([])
  })

  it('shows an explicit historical unavailable state instead of the active model diagram', async () => {
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(historyFixture(false)))} threadId="thr_history" />)
    fireEvent.click(await screen.findByRole('button', { name: /Regional Six Bus.*历史/ }))
    expect(await screen.findByText('历史电网视图暂不可用')).toBeTruthy()
    expect(screen.queryByRole('img', { name: '电网拓扑' })).toBeNull()
  })

  it('renders an idle Thread with the current IEEE-39 model and ordinary controls', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(screen.getByText('电网分析工作台')).toBeTruthy()
    expect(screen.queryByText('CAPSTONE / AGENT WORKSPACE')).toBeNull()
    expect(screen.getByRole('heading', { name: '智能体对话' })).toBeTruthy()
    expect(screen.getByRole('img', { name: '工业专业框架与 AI 智能体应用的连接示意' })).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.getByText('CAPABILITY / EVIDENCE / CONTROL')).toBeTruthy()
    expect(screen.getByTestId('assistant-ui-chat')).toBeTruthy()
    expect(screen.getByText(/IEEE-39 有哪些母线和线路/)).toBeTruthy()
    expect(screen.getByText(/对 IEEE-39 执行一次交流潮流/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '筛查负载率最高的三条线路。' }))
    expect(await screen.findByText('Fixture 已接收自动指令：筛查负载率最高的三条线路。')).toBeTruthy()
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('')
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(false)
    expect(document.querySelector('.network-model')?.textContent).toBe('IEEE-39')
    expect(screen.queryByText(/^模型历史/)).toBeNull()
  })

  it('keeps low-value state and internal identifiers out of the conversation heading', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    expect(screen.getByRole('heading', { name: '智能体对话' })).toBeTruthy()
    expect(screen.queryByText('THREAD / RUN run_001')).toBeNull()
    expect(screen.queryByRole('button', { name: '查看 Thread 详情' })).toBeNull()
    expect(document.querySelector('.thread-run-state')).toBeNull()
  })

  it('submits a model switch from the grid pane through the Thread command path', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    expect(screen.queryByRole('listbox', { name: '目标电网模型' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '模型目录' }))
    fireEvent.change(screen.getByRole('listbox', { name: '目标电网模型' }), { target: { value: 'pypsa39' } })
    expect(await screen.findByText('Fixture 已接收自动指令：打开 pypsa39 电网模型')).toBeTruthy()
  })

  it('routes an explicit model-open phrase through the canonical switch command', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '打开 pypsa39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText('Fixture 已接收自动指令：打开 pypsa39')).toBeTruthy()
  })

  it('does not reopen the active model unless the user explicitly requests a fresh context', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    render(<ThreadFixtureApp client={new CapstoneThreadClient({ ...transport, sendCommand: async (command) => { commands.push(command); return transport.sendCommand(command) } })} threadId="thr_demo_39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '打开 ieee39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('Fixture 已接收自动指令：打开 ieee39')).toBeTruthy()
    expect(screen.queryByText('switch_model · accepted')).toBeNull()
    expect(commands.map((command) => command.kind)).toEqual(['send_auto'])

    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '重新打开 ieee39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('Fixture 已接收自动指令：重新打开 ieee39')).toBeTruthy()
    expect(commands.slice(1).map((command) => command.kind)).toEqual(['reopen_model_context', 'send_auto'])
    expect(commands[1].payload.reason).toBe('user_requested_fresh_context')
  })

  it('keeps a longer open-and-analyze request as ordinary agent work', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    const request = '打开 IEEE-39 网络并解析线路 11 的端点。'
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText(`Fixture 已接收自动指令：${request}`)).toBeTruthy()
  })

  it.each(['打开 不存在模型', '打开 case24_ieee_rts 电网模型'])('sends an unresolved model request through the conversation: %s', async (request) => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText(request)).toBeTruthy()
    expect(await screen.findByText(`Fixture 已接收自动指令：${request}`)).toBeTruthy()
    expect(commands).toHaveLength(1)
    expect(commands[0]).toMatchObject({ kind: 'send_auto', payload: { text: request } })
    expect(screen.queryByText(/未找到注册模型/)).toBeNull()
  })

  it('keeps an English analytical request on the ordinary route', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    const request = '打开 IEEE-39 network and analyze line 11'
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: request } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText(`Fixture 已接收自动指令：${request}`)).toBeTruthy()
  })

  it('sends ordinary conversation after all calculation tools are disabled', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    for (const checkbox of screen.getAllByRole('checkbox')) {
      if ((checkbox as HTMLInputElement).checked) fireEvent.click(checkbox)
    }
    fireEvent.click(screen.getByRole('button', { name: '保存工具选择' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '你好' } })
    await waitFor(() => expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('Fixture 已接收自动指令：你好')).toBeTruthy()
    expect(screen.queryByText(/未启用适用于此模型/)).toBeNull()
  })

  it('shows grid tools directly and preserves all-off selection', async () => {
    const fixture = structuredClone(threadUiFixture('idle-ieee39'))
    const snapshot = fixture.snapshot as { active_model_context: Record<string, unknown> }
    snapshot.active_model_context.enabled_profiles = { schema: 'capstone-model-capability-selection/1',
      enabled_profiles: [{ profile_id: 'pandapower-static-analysis', profile_version: '1.0.1' }] }
    render(<ThreadFixtureApp client={new CapstoneThreadClient(createFixtureTransport(fixture))} threadId="thr_demo_39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect(screen.queryByRole('button', { name: '历史回答' })).toBeNull()
    expect(screen.queryByText('自动路由')).toBeNull()
    expect(screen.queryByRole('button', { name: '选择 Profile' })).toBeNull()
    expect(screen.queryByText('高级')).toBeNull()
    expect(screen.queryByText('专业功能配置')).toBeNull()
    expect(screen.getByText('电网计算分析工具')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '保存工具选择' })).toBeNull()
    fireEvent.click(screen.getByRole('checkbox', { name: 'pandapower 静态分析' }))
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: '保存工具选择' }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: '保存工具选择' }))
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect((screen.getByRole('checkbox', { name: 'pandapower 静态分析' }) as HTMLInputElement).checked).toBe(false)
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).checked).toBe(true)
    expect(screen.queryByText('操作已提交。')).toBeNull()
  })

  it('keeps history actions inside Settings and per-answer activity accessible', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect(screen.getByRole('button', { name: '折叠历史回答' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '展开历史回答' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '隐藏运行过程' })).toBeNull()
    expect(screen.queryByRole('button', { name: '显示运行过程' })).toBeNull()
    expect(screen.queryByText('历史回答', { exact: true })).toBeNull()
    expect(screen.queryByText('仅已加载回答 · 新回答完整显示')).toBeNull()
  })

  it('closes the flat input settings menu when focus moves outside it', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect(document.querySelector('.thread-settings-menu.is-open')).toBeTruthy()
    fireEvent.click(document.body)
    expect(document.querySelector('.thread-settings-menu.is-open')).toBeNull()
  })

  it('projects a sent automatic instruction and fixture response into the chat', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)

    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    expect(await screen.findByText('查看当前模型')).toBeTruthy()
    expect(await screen.findByText('Fixture 已接收自动指令：查看当前模型')).toBeTruthy()
  })

  it('sends another instruction after the previous response completes', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    for (const text of ['查看当前模型', '继续查看线路']) {
      fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: text } })
      fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
      expect(await screen.findByText(`Fixture 已接收自动指令：${text}`)).toBeTruthy()
    }
  })

  it('sends another instruction after a same-model activating turn', async () => {
    render(<ThreadFixtureApp fixtureId="idle-ieee39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '打开 ieee39' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('Fixture 已接收自动指令：打开 ieee39')).toBeTruthy()
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText('Fixture 已接收自动指令：查看当前模型')).toBeTruthy()
    expect(screen.queryByText(/当前模型已经是/)).toBeNull()
  })

  it('uses new command identities when an existing Thread is reopened', async () => {
    const fixture = threadUiFixture('idle-ieee39')
    const transport = createFixtureTransport(fixture)
    const commands: ThreadCommand[] = []
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => {
      commands.push(command)
      return transport.sendCommand(command)
    } })
    const first = render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await screen.findByText('Fixture 已接收自动指令：查看当前模型')
    first.unmount()
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '继续查看线路' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands[1].command_id).not.toBe(commands[0].command_id)
    expect(commands[1].idempotency_key).not.toBe(commands[0].idempotency_key)
    expect(await screen.findByText('Fixture 已接收自动指令：继续查看线路')).toBeTruthy()
  })

  it('shows a rejected conversational command instead of silently discarding its receipt', async () => {
    const transport = createFixtureTransport(threadUiFixture('idle-ieee39'))
    const client = new CapstoneThreadClient({ ...transport, sendCommand: async (command) => ({
      schema: 'capstone-command-receipt/1', thread_id: command.thread_id,
      command_id: command.command_id, idempotency_key: command.idempotency_key,
      status: 'rejected', rejection: 'stale_event_seq',
    }) })
    render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '查看当前模型' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
    expect(await screen.findByText(/stale_event_seq/)).toBeTruthy()
    await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('查看当前模型'))
  })

  it('keeps live cancellation in the composer while the grid pane is historical', async () => {
    render(<ThreadFixtureApp fixtureId="historical-live-attempt" />)

    expect(await screen.findByText('历史页 · 只读视图')).toBeTruthy()
    expect(screen.queryByRole('alert', { name: 'event stream is not contiguous' })).toBeNull()
    expect(screen.getByRole('button', { name: '停止生成' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '取消当前计算' })).toBeNull()
    expect(screen.queryByRole('button', { name: '打开回放' })).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: '返回当前模型' })[0])
    await waitFor(() => expect(screen.queryByText('历史页 · 只读视图')).toBeNull())
    expect(document.querySelector('.network-model')?.textContent).toBe('IEEE-39')
  })

  it('freezes conversation controls behind the resync gate', async () => {
    render(<ThreadFixtureApp fixtureId="resync-required" />)

    expect((await screen.findAllByText('需要重新同步')).length).toBeGreaterThan(0)
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: '重新同步' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('需要重新同步').closest('.capstone-chat-viewport')).toBeTruthy()
    expect(document.querySelector('.thread-state-strip')).toBeNull()
  })

  it('exposes a new Attempt retry after interruption', async () => {
    render(<ThreadFixtureApp fixtureId="interrupted-attempt" />)

    expect(await screen.findByText('本次 Attempt 已中断')).toBeTruthy()
    expect(screen.getAllByText('本次 Attempt 已中断')).toHaveLength(1)
    expect(document.querySelector('.thread-interrupted-banner')).toBeNull()
    expect((screen.getByRole('button', { name: '重试新 Attempt' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByText(/line_12/)).toBeTruthy()
  })
})
