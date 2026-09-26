import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import type { CapstoneClient } from './api'
import type { Catalog, SessionEvent } from './types'
import { sampleView } from './networkFixture'

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
  it('requires explicit token, session start, and each ordered turn action', async () => {
    const { client, createSession, submitTurn } = mockClient()
    render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    expect(await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })).toBeTruthy()
    expect(screen.getByText('成本仅为模型目标值。')).toBeTruthy()
    expect(createSession).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '启动本轮分析' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith(
      'pypsa-business-cases', 'regional-demand-stress',
    ))
    expect(submitTurn).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByRole('button', { name: '提交指令 1' }))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledWith(
      'session-one', '打开模型。', expect.any(String),
    ))
  })

  it('starts automatic completion and allows stopping future steps', async () => {
    const { client, createSession, submitTurn } = mockClient()
    render(<App clientFactory={() => client} />)
    fireEvent.change(screen.getByLabelText('访问凭证'), { target: { value: 'private-token' } })
    fireEvent.click(screen.getByRole('button', { name: '连接工作台' }))
    await screen.findByRole('heading', { name: '区域负荷增长情景', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: '自动完成' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(submitTurn).toHaveBeenCalledWith(
      'session-one', '打开模型。', expect.any(String),
    ))
    fireEvent.click(screen.getByRole('button', { name: '停止自动执行' }))
    expect(screen.queryByRole('button', { name: '停止自动执行' })).toBeNull()
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
    fireEvent.click(screen.getByRole('button', { name: '启动本轮分析' }))
    await waitFor(() => expect(network).toHaveBeenCalledWith('session-one', 1))
    expect(await screen.findByRole('img', { name: '电网拓扑' })).toBeTruthy()
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
    fireEvent.click(screen.getByRole('button', { name: '启动本轮分析' }))
    expect(await screen.findByText('本轮电网视图暂不可用')).toBeTruthy()
    expect(screen.getByText('已打开模型。')).toBeTruthy()
  })
})
