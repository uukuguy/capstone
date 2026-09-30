import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App, { readerAnswerText } from './App'
import type { CapstoneClient } from './api'
import type { Catalog, SessionEvent } from './types'
import { sampleDiagramView, sampleView } from './networkFixture'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
beforeEach(() => vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(
  new Response(JSON.stringify({ token: 'public-demo-token-with-enough-length' })),
))))

const catalog: Catalog = {
  schema: 'capstone-catalog/1.0',
  applications: [{
    application_id: 'pypsa-business-cases', title: 'PyPSA 业务案例',
    cases: [{
      case_id: 'regional-demand-stress', title: '区域负荷增长情景',
      summary: '比较基准与增长情景。', model_origin: 'regional-six-bus',
      scenario_assumption: '三个时段各增加 10 MW。',
      interpretation_boundary: '成本仅为模型目标值。',
      instructions: ['打开模型。', '增加负荷。', '比较结果。'],
    }],
  }],
}

function mockClient(eventFlow?: (_id: string, _after: number,
  signal: AbortSignal) => AsyncGenerator<SessionEvent>) {
  const submitTurn = vi.fn().mockResolvedValue({ session_id: 'session-one', ordinal: 1, state: 'accepted' })
  const createSession = vi.fn().mockResolvedValue({
    session_id: 'session-one', run_id: null,
    application_id: 'pypsa-business-cases', state: 'pending',
  })
  const client = {
    catalog: vi.fn().mockResolvedValue(catalog),
    createSession,
    submitTurn,
    turn: vi.fn().mockImplementation(async (_sid: string, ordinal: number) => ({
      ordinal, turn_id: `turn-${ordinal}`, answer_output: `回答 ${ordinal}`,
      answer_ref: `answer:${ordinal}`, result_refs: [], evidence_refs: [],
    })),
    network: vi.fn().mockResolvedValue(sampleView),
    caseDiagram: vi.fn().mockResolvedValue(sampleDiagramView.diagram),
    close: vi.fn().mockResolvedValue({ session_id: 'session-one', state: 'closing' }),
    status: vi.fn().mockResolvedValue({
      session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
      state: 'ready', error_code: null, accepted_turns: 0, completed_turns: 0,
    }),
    events: eventFlow || (async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
              sequence: 1, event: 'ready', payload: { run_id: 'run-one' } }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }),
  }
  return { client: client as unknown as CapstoneClient, createSession, submitTurn, network: client.network }
}

describe('operator workflow', () => {
  it('replaces scripted demo echo text with concise reader-facing copy', () => {
    const turn = {
      ordinal: 1, turn_id: 'turn-one',
      answer_output: 'scripted semantic execution completed for question 1: 打开模型。',
      answer_ref: 'answer:one', result_refs: ['result:one'], evidence_refs: ['evidence:one'],
    }
    expect(readerAnswerText(turn)).toBe('本步已完成，结果与证据已写入当前运行。')
    expect(readerAnswerText({ ...turn, answer_output: '已打开模型。' })).toBe('已打开模型。')
  })

  it('opens the demo workspace automatically without a login screen', async () => {
    const token = 'public-demo-token-with-enough-length'
    const { client } = mockClient()
    const factory = vi.fn(() => client)
    render(<App clientFactory={factory} />)
    expect(screen.queryByLabelText('访问凭证')).toBeNull()
    expect(await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })).toBeTruthy()
    expect(screen.getByText('CAPABILITY / EVIDENCE / CONTROL')).toBeTruthy()
    expect(screen.getByText('CASE LIBRARY')).toBeTruthy()
    expect(screen.queryByText('已登记案例')).toBeNull()
    expect(factory).toHaveBeenCalledWith(token)
  })

  it('switches long overview facts to stacked rows while keeping short facts compact', async () => {
    const { client } = mockClient()
    const longCase: Catalog = {
      ...catalog,
      applications: [{
        ...catalog.applications[0],
        cases: [{
          ...catalog.applications[0].cases[0],
          scenario_assumption: '按案例固定指令和登记模型进行本轮计算。',
          interpretation_boundary: '仅说明本次登记模型及静态仿真结果；不代表实时运行状态或运行许可。',
        }],
      }],
    }
    client.catalog = vi.fn().mockResolvedValue(longCase)
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    const facts = [...document.querySelectorAll<HTMLElement>('.case-overview-fact')]
    const factByValue = (value: string) => facts.find((fact) => fact.textContent?.includes(value))
    expect(factByValue('regional-six-bus')?.classList.contains('is-long')).toBe(false)
    expect(factByValue('3 步')?.classList.contains('is-long')).toBe(false)
    expect(factByValue('按案例固定指令和登记模型进行本轮计算。')?.classList.contains('is-long')).toBe(true)
    expect(factByValue('仅说明本次登记模型及静态仿真结果；不代表实时运行状态或运行许可。')
      ?.classList.contains('is-long')).toBe(true)
  })

  it('opens the demo workspace again after a page reload', async () => {
    const { client, createSession } = mockClient()
    const factory = vi.fn(() => client)
    const first = render(<App clientFactory={factory} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    first.unmount()
    render(<App clientFactory={factory} />)
    expect(screen.queryByLabelText('访问凭证')).toBeNull()
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    expect(factory).toHaveBeenCalledTimes(2)
    expect(createSession).not.toHaveBeenCalled()
  })

  it('restores an existing run after reload without creating another session', async () => {
    const sessionId = 'session-0123456789abcdef01234567'
    const { client, submitTurn } = mockClient()
    const createSession = vi.fn().mockResolvedValue({ session_id: sessionId, run_id: null,
      application_id: 'pypsa-business-cases', state: 'pending' })
    const status = vi.fn().mockResolvedValue({ session_id: sessionId, run_id: 'run-one',
      application_id: 'pypsa-business-cases', state: 'ready', error_code: null,
      accepted_turns: 1, completed_turns: 1 })
    Object.assign(client, { createSession, status,
      events: async function* (_id: string, _after: number, signal: AbortSignal) {
        await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
      },
    })
    const first = render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(1))
    first.unmount()
    render(<App clientFactory={() => client} />)
    expect(await screen.findByRole('button', { name: '执行指令 2' })).toBeTruthy()
    expect(createSession).toHaveBeenCalledTimes(1)
    expect(status).toHaveBeenCalledWith(sessionId)
  })

  it('opens the demo workspace on the first navigation', async () => {
    const { client } = mockClient()
    render(<App clientFactory={() => client} />)
    expect(screen.queryByLabelText('访问凭证')).toBeNull()
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
  })

  it('offers retry without asking for a credential when the demo service is unavailable', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error('暂时不可用')).mockResolvedValue(
      new Response(JSON.stringify({ token: 'public-demo-token-with-enough-length' })),
    )
    vi.stubGlobal('fetch', fetch)
    const { client } = mockClient()
    render(<App clientFactory={() => client} />)
    expect(screen.queryByLabelText('访问凭证')).toBeNull()
    fireEvent.click(await screen.findByRole('button', { name: '重试连接' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('retries an unavailable case diagram only after reopening that case', async () => {
    const twoCases: Catalog = { ...catalog, applications: [{ ...catalog.applications[0],
      cases: [...catalog.applications[0].cases, {
        ...catalog.applications[0].cases[0], case_id: 'case-b', title: '案例 B',
      }],
    }] }
    const client = {
      ...mockClient().client,
      catalog: vi.fn().mockResolvedValue(twoCases),
      caseDiagram: vi.fn().mockRejectedValue(new Error('preview unavailable')),
    } as unknown as CapstoneClient
    render(<App clientFactory={() => client} />)
    expect(await screen.findByText('案例电网暂不可用')).toBeTruthy()
    expect(client.caseDiagram).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /案例 B/ }))
    expect(await screen.findByRole('heading', { name: '案例 B', level: 1 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /区域负荷增长情景/ }))
    await waitFor(() => expect(client.caseDiagram).toHaveBeenCalledTimes(3))
  })

  it('restores the latest session while keeping the topology preview static', async () => {
    const twoCases: Catalog = { ...catalog, applications: [{ ...catalog.applications[0],
      cases: [...catalog.applications[0].cases, {
        ...catalog.applications[0].cases[0], case_id: 'case-b', title: '案例 B',
      }],
    }] }
    const createSession = vi.fn().mockResolvedValue({
      session_id: 'session-a', run_id: null, application_id: 'pypsa-business-cases', state: 'pending',
    })
    const client = {
      catalog: vi.fn().mockResolvedValue(twoCases), createSession,
      status: vi.fn().mockResolvedValue({ session_id: 'session-a', run_id: 'run-a',
        application_id: 'pypsa-business-cases', state: 'ready', error_code: null,
        accepted_turns: 1, completed_turns: 1 }),
      network: vi.fn().mockResolvedValue(sampleView),
      caseDiagram: vi.fn().mockResolvedValue(sampleDiagramView.diagram),
      events: async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
        yield { schema: 'capstone-session-event/1.0', session_id: 'session-a', sequence: 1,
          event: 'ready', payload: { run_id: 'run-a' } }
        yield { schema: 'capstone-session-event/1.0', session_id: 'session-a', sequence: 2,
          event: 'answer_committed', payload: { ordinal: 1, turn_id: 'turn-a',
            answer_output: '已打开模型。', answer_ref: 'answer:a', result_refs: [], evidence_refs: [] } }
        yield { schema: 'capstone-session-event/1.0', session_id: 'session-a', sequence: 3,
          event: 'network_view', payload: { ordinal: 1 } }
        await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
      },
    } as unknown as CapstoneClient
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByText('已打开模型。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /案例 B/ }))
    expect(await screen.findByRole('heading', { name: '案例 B', level: 1 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /区域负荷增长情景/ }))
    expect(await screen.findByText('已打开模型。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '查看指令 1 的电网' })).toBeNull()
    expect(createSession).toHaveBeenCalledTimes(1)
  })

  it('continues automatic execution when another case is selected', async () => {
    const twoCases: Catalog = { ...catalog, applications: [{ ...catalog.applications[0],
      cases: [...catalog.applications[0].cases, {
        ...catalog.applications[0].cases[0], case_id: 'case-b', title: '案例 B',
      }],
    }] }
    let completed = 0
    let closed = false
    const createSession = vi.fn().mockResolvedValue({ session_id: 'session-a', run_id: 'run-a',
      application_id: 'pypsa-business-cases', state: 'ready' })
    const submitTurn = vi.fn().mockImplementation(async () => { completed += 1 })
    const network = vi.fn().mockImplementation(async (_sid: string, ordinal: number) => ({ ...sampleView, ordinal }))
    const client = {
      catalog: vi.fn().mockResolvedValue(twoCases), createSession, submitTurn,
      turn: vi.fn().mockImplementation(async (_sid: string, ordinal: number) => ({
        ordinal, turn_id: `turn-${ordinal}`, answer_output: `回答 ${ordinal}`,
        answer_ref: `answer:${ordinal}`, result_refs: [], evidence_refs: [],
      })),
      network,
      caseDiagram: vi.fn().mockResolvedValue(sampleDiagramView.diagram),
      status: vi.fn().mockImplementation(async () => ({ session_id: 'session-a', run_id: 'run-a',
        application_id: 'pypsa-business-cases', state: closed ? 'completed' : 'ready', error_code: null,
        accepted_turns: completed, completed_turns: completed })),
      close: vi.fn().mockImplementation(async () => { closed = true }),
      report: vi.fn().mockResolvedValue('报告'), result: vi.fn().mockResolvedValue({}),
      events: async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
        let emitted = 0
        while (!signal.aborted) {
          if (completed > emitted) {
            const ordinal = ++emitted
            yield { schema: 'capstone-session-event/1.0', session_id: 'session-a',
              sequence: ordinal * 2 - 1, event: 'answer_committed', payload: {
                ordinal, turn_id: `turn-${ordinal}`, answer_output: `回答 ${ordinal}`,
                answer_ref: `answer:${ordinal}`, result_refs: [], evidence_refs: [],
              } }
            yield { schema: 'capstone-session-event/1.0', session_id: 'session-a',
              sequence: ordinal * 2, event: 'network_view', payload: { ordinal } }
          } else {
            await new Promise((resolve) => setTimeout(resolve, 10))
          }
        }
      },
    } as unknown as CapstoneClient
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(1))
    expect((await screen.findAllByText('TOPOLOGY / VIEW')).length).toBeGreaterThan(0)
    expect(network).not.toHaveBeenCalled()
    expect(submitTurn).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /案例 B/ }))
    await screen.findByRole('heading', { name: '案例 B', level: 1 })
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(2), { timeout: 3000 })
    fireEvent.click(screen.getByRole('button', { name: /区域负荷增长情景/ }))
    expect(createSession).toHaveBeenCalledTimes(1)
  })

  it('shows the completed report at the end of the central workflow', async () => {
    const flow = async function* (): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 1, event: 'completed', payload: {} }
    }
    const { client } = mockClient(flow)
    Object.assign(client, {
      report: vi.fn().mockResolvedValue('# 本轮报告\n分析已完成。\n###### 已登记网络核对结果\n**来源**\n| 类型 | 数量 |\n| --- | --- |\n| 母线 | 6 |'),
      result: vi.fn().mockResolvedValue({ completed: true }),
    })
    const { container } = render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    const report = await screen.findByRole('region', { name: '分析报告' })
    expect(report.textContent).toContain('分析已完成。')
    expect(screen.getByRole('heading', { name: '已登记网络核对结果', level: 6 })).toBeTruthy()
    expect(report.textContent).toContain('来源')
    expect(report.textContent).not.toContain('**来源**')
    expect(screen.getByRole('table')).toBeTruthy()
    expect(container.querySelector('.workspace-center')?.contains(report)).toBe(true)
    expect(report.compareDocumentPosition(container.querySelector('.run-action-bar')!) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    expect(screen.queryByRole('tab', { name: '报告' })).toBeNull()
  })

  it('links each completed timeline step to its replayed topology snapshot', async () => {
    const story = {
      schema: 'capstone-network-story/1.0' as const,
      mode: 'cumulative-snapshots' as const,
      story_status: 'complete' as const,
      plan_source: 'fallback' as const,
      diagram: sampleDiagramView.diagram,
      steps: [1, 2, 3].map((ordinal) => ({
        schema: 'capstone-network-story-step/1.0' as const,
        ordinal,
        diagram_ref: sampleDiagramView.diagram.ref,
        model_revision: sampleDiagramView.diagram.model.revision,
        current_focus_ids: [ordinal === 1 ? 'line:1' : 'transformer:2'],
        history_focus_ids: ordinal === 1 ? [] : ['line:1'],
        overlay: null,
        plan_source: 'fallback' as const,
      })),
    }
    const flow = async function* (): AsyncGenerator<SessionEvent> {
      for (let ordinal = 1; ordinal <= 3; ordinal += 1) {
        yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
          sequence: ordinal, event: 'answer_committed', payload: {
            ordinal, turn_id: `turn-${ordinal}`, answer_output: `回答 ${ordinal}`,
            answer_ref: `answer:${ordinal}`, result_refs: [], evidence_refs: [],
          } }
      }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 4, event: 'completed', payload: {} }
    }
    const { client } = mockClient(flow)
    Object.assign(client, {
      report: vi.fn().mockResolvedValue('# 本轮报告'),
      result: vi.fn().mockResolvedValue({ completed: true }),
      networkStory: vi.fn().mockResolvedValue(story),
    })
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    await screen.findByRole('button', { name: '查看步骤 1 的电气拓扑' })
    expect(document.querySelector('.network-step')?.textContent).toBe('指令 3')
    fireEvent.click(screen.getByRole('button', { name: '查看步骤 1 的电气拓扑' }))
    expect(document.querySelector('.network-step')?.textContent).toBe('指令 1')
  })

  it('returns a completed case to its initial manual or automatic choice', async () => {
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 1, event: 'completed', payload: {} }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client, createSession } = mockClient(flow)
    Object.assign(client, { report: vi.fn().mockResolvedValue('# 本轮报告'),
      result: vi.fn().mockResolvedValue({ completed: true }) })
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByRole('region', { name: '分析报告' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '再次分析' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重置案例' }))
    expect(createSession).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('region', { name: '分析报告' })).toBeNull()
    expect(screen.getByRole('button', { name: '执行指令 1' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '自动完成' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledTimes(2))
  })

  it('shows the case network before a run and starts the first manual turn with one click', async () => {
    const { client, createSession, submitTurn } = mockClient()
    render(<App clientFactory={() => client} />)
    expect(await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })).toBeTruthy()
    expect(await screen.findByText(/3 母线 \/ 2 支路/)).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.getByText('成本仅为模型目标值。')).toBeTruthy()
    expect(createSession).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith(
      'pypsa-business-cases', 'regional-demand-stress', expect.any(String),
    ))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledWith(
      'session-one', '打开模型。', expect.any(String),
    ))
    await waitFor(() => expect(screen.queryByRole('button', { name: '执行指令 1' })).toBeNull())
  })

  it('starts automatic completion and allows stopping future steps', async () => {
    const { client, createSession, submitTurn } = mockClient()
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    const projectLink = screen.getByRole('link', { name: '在 GitHub 查看 CAPSTONE 项目源代码' })
    expect(projectLink.getAttribute('href')).toBe('https://github.com/uukuguy/capstone')
    expect(projectLink.getAttribute('target')).toBe('_blank')
    expect(screen.getByRole('link', { name: '打开 Thread' }).getAttribute('href')).toBe('?thread=new')
    expect(screen.getByRole('img', { name: '工业专业框架与 AI 智能体应用的连接示意' })).toBeTruthy()
    expect(screen.getByText('pandapower')).toBeTruthy()
    expect(screen.getByText('PyPSA')).toBeTruthy()
    expect(screen.getByText(/CAPSTONE 为电网科学AI提供应用底座/)).toBeTruthy()
    expect(screen.getByText(/SCIENTIFIC AI FOR THE GRID/)).toBeTruthy()
    expect(screen.getByText(/DeepONet.*FNO/)).toBeTruthy()
    expect(screen.getByText(/Neural-DAE.*Koopman/)).toBeTruthy()
    expect(screen.getByText(/GraphGPS.*PI-GNN/)).toBeTruthy()
    const automatic = screen.getByRole('button', { name: '自动完成' })
    const manual = screen.getByRole('button', { name: '执行指令 1' })
    expect(automatic.className).toContain('primary-button')
    expect(manual.className).toContain('secondary-button')
    expect(manual.compareDocumentPosition(automatic) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledWith(
      'session-one', '打开模型。', expect.any(String),
    ))
    fireEvent.click(screen.getByRole('button', { name: '停止自动执行' }))
    expect(screen.queryByRole('button', { name: '停止自动执行' })).toBeNull()
    expect(screen.getByRole('status').textContent).toContain('后续不会自动提交')
  })

  it('loads the completed topology story when automatic polling observes completion', async () => {
    const { client, submitTurn } = mockClient()
    let statusCalls = 0
    const story = {
      schema: 'capstone-network-story/1.0' as const,
      mode: 'cumulative-snapshots' as const,
      story_status: 'partial' as const,
      plan_source: 'fallback' as const,
      diagram: sampleDiagramView.diagram,
      steps: [{
        schema: 'capstone-network-story-step/1.0' as const,
        ordinal: 1,
        diagram_ref: sampleDiagramView.diagram.ref,
        model_revision: sampleDiagramView.diagram.model.revision,
        current_focus_ids: ['line:1'], history_focus_ids: [], overlay: null,
        plan_source: 'fallback' as const,
      }],
    }
    Object.assign(client, {
      status: vi.fn().mockImplementation(async () => {
        statusCalls += 1
        return statusCalls === 1
          ? { session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
              state: 'ready', error_code: null, accepted_turns: 0, completed_turns: 0 }
          : { session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
              state: 'completed', error_code: null, accepted_turns: 1, completed_turns: 1 }
      }),
      report: vi.fn().mockResolvedValue('# 本轮报告'),
      result: vi.fn().mockResolvedValue({ completed: true }),
      networkStory: vi.fn().mockResolvedValue(story),
    })
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(client.networkStory).toHaveBeenCalledWith('session-one'))
    expect(await screen.findByRole('button', { name: '步骤 1' })).toBeTruthy()
  })

  it('keeps the accepted instruction running after stop without submitting the next one', async () => {
    let releaseAnswer: (() => void) | undefined
    const answerReady = new Promise<void>((resolve) => { releaseAnswer = resolve })
    let accepted = 0
    let completed = 0
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 1,
        event: 'ready', payload: { run_id: 'run-one' } }
      await answerReady
      completed = 1
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 2,
        event: 'answer_committed', payload: { ordinal: 1, turn_id: 'turn-one',
          answer_output: '第一步完成。', answer_ref: 'answer:1', result_refs: [], evidence_refs: [] } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 3,
        event: 'network_view_unavailable', payload: { ordinal: 1 } }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client } = mockClient(flow)
    const submitTurn = vi.fn().mockImplementation(async () => { accepted += 1 })
    Object.assign(client, { submitTurn,
      status: vi.fn().mockImplementation(async () => ({
        session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
        state: accepted > completed ? 'executing' : 'ready', error_code: null,
        accepted_turns: accepted, completed_turns: completed,
      })),
    })
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(1))
    await screen.findByText('正在执行当前指令…')
    fireEvent.click(screen.getByRole('button', { name: '停止自动执行' }))
    expect(screen.getByRole('status').textContent).toContain('当前指令仍会完成')
    releaseAnswer?.()
    expect(await screen.findByRole('button', { name: '执行指令 2' })).toBeTruthy()
    expect(submitTurn).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status').textContent).toContain('后续不会自动提交')
  })

  it('explains an idle session timeout while preserving the completed steps', async () => {
    const { client } = mockClient()
    Object.assign(client, { status: vi.fn().mockResolvedValue({
      session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
      state: 'interrupted', error_code: 'session_idle_timeout',
      accepted_turns: 1, completed_turns: 1,
    }) })
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    expect((await screen.findAllByText('会话已超时')).length).toBe(2)
    expect(screen.getByText(/已完成步骤仍可回看/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '重置案例' })).toBeTruthy()
  })

  it('explains capacity eviction and offers a fresh run', async () => {
    const { client } = mockClient()
    Object.assign(client, { status: vi.fn().mockResolvedValue({
      session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
      state: 'interrupted', error_code: 'session_capacity_evicted',
      accepted_turns: 0, completed_turns: 0,
    }) })
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    expect((await screen.findAllByText('空闲会话已让位')).length).toBe(2)
    expect(screen.getByText(/有新分析需要运行/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '重置案例' })).toBeTruthy()
  })

  it('offers only report generation after all steps are complete', async () => {
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      for (let ordinal = 1; ordinal <= 3; ordinal += 1) {
        yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
          sequence: ordinal, event: 'answer_committed', payload: {
            ordinal, turn_id: `turn-${ordinal}`, answer_output: `回答 ${ordinal}`,
            answer_ref: `answer:${ordinal}`, result_refs: [], evidence_refs: [],
            ...(ordinal === 1 ? { duration_ms: 4200 } : {}),
          } }
      }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client } = mockClient(flow)
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByRole('button', { name: '生成报告' })).toBeTruthy()
    expect(screen.getByText('已完成 · 4.2 秒')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '自动完成' })).toBeNull()
  })

  it('keeps the static case diagram when a projection event is emitted', async () => {
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 1, event: 'ready', payload: { run_id: 'run-one' } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 2, event: 'answer_committed', payload: {
          ordinal: 1, turn_id: 'turn-one', answer_output: '已打开模型。',
          answer_ref: 'answer:one', result_refs: [], evidence_refs: [],
        } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 3, event: 'network_view', payload: { ordinal: 1 } }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client, network } = mockClient(flow)
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(network).not.toHaveBeenCalled()
  })

  it('keeps a complete model diagram across a step without a new network layer', async () => {
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 1,
        event: 'ready', payload: { run_id: 'run-one' } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 2,
        event: 'answer_committed', payload: { ordinal: 1, turn_id: 'turn-one', answer_output: '已打开模型。',
          answer_ref: 'answer:one', result_refs: [], evidence_refs: [] } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 3,
        event: 'network_layer', payload: { ordinal: 1 } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 4,
        event: 'answer_committed', payload: { ordinal: 2, turn_id: 'turn-two', answer_output: '已分析情景。',
          answer_ref: 'answer:two', result_refs: [], evidence_refs: [] } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one', sequence: 5,
        event: 'network_layer_unavailable', payload: { ordinal: 2 } }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client, network } = mockClient(flow)
    network.mockResolvedValue(sampleDiagramView)
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByText('已分析情景。')).toBeTruthy()
    expect(await screen.findByText(/3 母线 \/ 2 支路/)).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '查看指令 1 的电网' })).toBeNull()
    expect(screen.queryByRole('button', { name: '回到最新步骤' })).toBeNull()
    expect(network).not.toHaveBeenCalled()
  })

  it('keeps the answer visible when the authority cannot project a network', async () => {
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 1, event: 'answer_committed', payload: {
          ordinal: 1, turn_id: 'turn-one', answer_output: '已打开模型。',
          answer_ref: 'answer:one', result_refs: [], evidence_refs: [],
        } }
      yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
        sequence: 2, event: 'network_view_unavailable', payload: { ordinal: 1 } }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client } = mockClient(flow)
    render(<App clientFactory={() => client} />)
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByText('已打开模型。')).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
  })
})
