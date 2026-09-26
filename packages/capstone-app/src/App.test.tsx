import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import type { CapstoneClient } from './api'
import type { Catalog, SessionEvent } from './types'
import { sampleDiagramView, sampleView } from './networkFixture'

afterEach(cleanup)

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
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    expect(await screen.findByText('案例电网暂不可用')).toBeTruthy()
    expect(client.caseDiagram).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: /案例 B/ }))
    expect(await screen.findByRole('heading', { name: '案例 B', level: 1 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /区域负荷增长情景/ }))
    await waitFor(() => expect(client.caseDiagram).toHaveBeenCalledTimes(3))
  })

  it('restores the latest session and selected completed step after switching cases', async () => {
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
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByText('已打开模型。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '查看指令 1 的电网' }))
    fireEvent.click(screen.getByRole('button', { name: /案例 B/ }))
    expect(await screen.findByRole('heading', { name: '案例 B', level: 1 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /区域负荷增长情景/ }))
    expect(await screen.findByText('已打开模型。')).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看指令 1 的电网' }).getAttribute('aria-pressed')).toBe('true')
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
    const client = {
      catalog: vi.fn().mockResolvedValue(twoCases), createSession, submitTurn,
      caseDiagram: vi.fn().mockResolvedValue(sampleDiagramView.diagram),
      status: vi.fn().mockImplementation(async () => ({ session_id: 'session-a', run_id: 'run-a',
        application_id: 'pypsa-business-cases', state: closed ? 'completed' : 'ready', error_code: null,
        accepted_turns: completed, completed_turns: completed })),
      close: vi.fn().mockImplementation(async () => { closed = true }),
      report: vi.fn().mockResolvedValue('报告'), result: vi.fn().mockResolvedValue({}),
      events: async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
        await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
      },
    } as unknown as CapstoneClient
    render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: /案例 B/ }))
    await screen.findByRole('heading', { name: '案例 B', level: 1 })
    await waitFor(() => expect(submitTurn).toHaveBeenCalledTimes(2))
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
      report: vi.fn().mockResolvedValue('# 本轮报告\n分析已完成。'),
      result: vi.fn().mockResolvedValue({ completed: true }),
    })
    const { container } = render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    const report = await screen.findByRole('region', { name: '本轮分析报告' })
    expect(report.textContent).toContain('分析已完成。')
    expect(container.querySelector('.workspace-center')?.contains(report)).toBe(true)
    expect(report.compareDocumentPosition(container.querySelector('.run-action-bar')!) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    expect(screen.queryByRole('tab', { name: '报告' })).toBeNull()
  })

  it('shows the case network before a run and starts the first manual turn with one click', async () => {
    const { client, createSession, submitTurn } = mockClient()
    render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    expect(await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })).toBeTruthy()
    expect(await screen.findByText(/3 母线 \/ 2 支路/)).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.queryByText('成本仅为模型目标值。')).toBeNull()
    expect(createSession).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith(
      'pypsa-business-cases', 'regional-demand-stress',
    ))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledWith(
      'session-one', '打开模型。', expect.any(String),
    ))
    await waitFor(() => expect(screen.queryByRole('button', { name: '执行指令 1' })).toBeNull())
  })

  it('starts automatic completion and allows stopping future steps', async () => {
    const { client, createSession, submitTurn } = mockClient()
    render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    expect(screen.getByRole('img', { name: '工业专业框架与 AI 智能体应用的连接示意' })).toBeTruthy()
    expect(screen.getByText('pandapower')).toBeTruthy()
    expect(screen.getByText('PyPSA')).toBeTruthy()
    expect(screen.getByText(/CAPSTONE 为电力科学 AI 提供应用底座/)).toBeTruthy()
    expect(screen.getByText(/电力科学AI \/ PHYSICS-DRIVEN AI/)).toBeTruthy()
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
  })

  it('offers only report generation after all steps are complete', async () => {
    const flow = async function* (_id: string, _after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
      for (let ordinal = 1; ordinal <= 3; ordinal += 1) {
        yield { schema: 'capstone-session-event/1.0', session_id: 'session-one',
          sequence: ordinal, event: 'answer_committed', payload: {
            ordinal, turn_id: `turn-${ordinal}`, answer_output: `回答 ${ordinal}`,
            answer_ref: `answer:${ordinal}`, result_refs: [], evidence_refs: [],
          } }
      }
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
    }
    const { client } = mockClient(flow)
    render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByRole('button', { name: '生成报告' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '自动完成' })).toBeNull()
  })

  it('loads the authenticated network projection after a committed step', async () => {
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
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    await waitFor(() => expect(network).toHaveBeenCalledWith('session-one', 1))
    expect(await screen.findByRole('img', { name: '电网拓扑' })).toBeTruthy()
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
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByText('已分析情景。')).toBeTruthy()
    expect(await screen.findByText(/3 母线 \/ 2 支路/)).toBeTruthy()
    expect(screen.getByText('当前步骤暂无逐元件数值')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '查看指令 1 的电网' }))
    expect(screen.getByRole('button', { name: '查看指令 1 的电网' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: '回到最新步骤' })).toBeTruthy()
    expect(network).toHaveBeenCalledWith('session-one', 1)
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
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '执行指令 1' }))
    expect(await screen.findByText('已打开模型。')).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
  })
})
