import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadFixtureApp from './ThreadFixtureApp'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import { CapstoneThreadClient, type ThreadTransport } from './threadClient'
import { ThreadCasePicker, ThreadCaseProgress } from './CapstoneAssistantThread'
import type { CaseExecutionSnapshot } from './threadProtocol'

afterEach(cleanup)

const blockedCase: CaseExecutionSnapshot = {
  displayName: 'IEEE-39 潮流与线路筛查', status: 'blocked', completedSteps: 1, totalSteps: 3, currentStep: 2,
  steps: [
    { ordinal: 1, title: '打开 IEEE-39 模型', status: 'completed', durationMs: 1200, details: {} },
    { ordinal: 2, title: '执行交流潮流', status: 'failed', durationMs: null, details: { startedAt: '2026-10-02T00:00:00Z' } },
    { ordinal: 3, title: '筛查线路负载率', status: 'pending', durationMs: null, details: {} },
  ],
  actions: [
    { actionId: 'retry_case_step', label: '重试此步骤', enabled: true },
    { actionId: 'cancel_case', label: '停止案例', enabled: true },
  ],
  disabledReasons: ['运行被中断'],
}

const idleCase: CaseExecutionSnapshot = {
  displayName: 'IEEE-39 潮流与线路筛查', status: 'idle', completedSteps: 0, totalSteps: 3, currentStep: null,
  steps: [1, 2, 3].map((ordinal) => ({ ordinal, title: `步骤 ${ordinal}`, status: 'pending' as const, durationMs: null, details: {} })),
  actions: [{ actionId: 'start_case', label: '开始案例', enabled: true }], disabledReasons: [],
}

describe('Thread native Case interaction', () => {
  it('shows a blocked step beside its retry action', () => {
    render(<ThreadCaseProgress execution={blockedCase} onAction={vi.fn()} />)
    expect(screen.getByText('步骤 2 未完成')).toBeTruthy()
    expect((screen.getByRole('button', { name: '重试此步骤' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: '停止案例' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getAllByText('运行被中断').length).toBeGreaterThan(0)
  })

  it('shows progress and running duration beside the current step', () => {
    const running = { ...blockedCase, status: 'running' as const, completedSteps: 1, currentStep: 2,
      steps: blockedCase.steps.map((step) => step.ordinal === 2 ? { ...step, status: 'running' as const, durationMs: 12_400 } : step),
      actions: [{ actionId: 'cancel_case' as const, label: '停止案例', enabled: true }], disabledReasons: [] }
    render(<ThreadCaseProgress execution={running} onAction={vi.fn()} />)
    expect(screen.getByText('案例执行中 · 1 / 3')).toBeTruthy()
    expect(screen.getByText(/运行中 12\.4s/)).toBeTruthy()
  })

  it('keeps unavailable actions visible with their disabled reason during resync', () => {
    render(<ThreadCaseProgress execution={blockedCase} connection="resync_required" onAction={vi.fn()} />)
    expect(screen.getByText('需要重新同步')).toBeTruthy()
    expect((screen.getByRole('button', { name: '重试此步骤' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('先重新同步 Thread 后才能操作案例')).toBeTruthy()
  })

  it('exposes completed process details without showing internal ids by default', () => {
    const completed = { ...idleCase, status: 'completed' as const, completedSteps: 3, currentStep: null,
      steps: idleCase.steps.map((step) => ({ ...step, status: 'completed' as const, durationMs: 1000, details: { attempt_id: 'attempt_secret', answer: '完成' } })),
      actions: [{ actionId: 'view_case_details' as const, label: '查看案例过程', enabled: true }] }
    render(<ThreadCaseProgress execution={completed} onAction={vi.fn()} />)
    expect(screen.getByText(/案例已完成 · 3 \/ 3 步 · 总运行时长/)).toBeTruthy()
    expect(screen.queryByText('attempt_secret')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看案例过程' }))
    expect(screen.getByRole('region', { name: '案例过程详情' })).toBeTruthy()
    expect(screen.getAllByText('attempt_secret').length).toBeGreaterThan(0)
  })

  it('starts a registered case from the compact picker', () => {
    const onStart = vi.fn()
    render(<ThreadCasePicker cases={[{ caseId: 'pandapower-scripted-task', caseVersion: '1', displayName: 'IEEE-39 潮流与线路筛查', summary: '三步分析', modelIds: ['ieee39'], stepCount: 3 }]} onStart={onStart} />)
    fireEvent.click(screen.getByRole('button', { name: '开始案例' }))
    expect(onStart).toHaveBeenCalledWith('pandapower-scripted-task', '1')
  })

  it('dispatches blocked retry through the current Thread event cursor', async () => {
    const snapshot = {
      schema: 'capstone-thread-snapshot/1', thread_id: 'thr_case',
      run: { run_id: 'run_case', state: 'open' },
      active_model_context: { id: 'ctx_ieee39', model_id: 'ieee39', model_revision: '7', implementation_family: 'pandapower', selection_revision: 'sel_2' },
      active_grid_page_id: 'page_ieee39', current_attempt: null, last_event_seq: 12, base_event_seq: 12,
      application_state: { case_execution: {
        display_name: 'IEEE-39 潮流与线路筛查', status: 'blocked', completed_steps: 1, total_steps: 2, current_step: 2,
        steps: [
          { ordinal: 1, title: '打开 IEEE-39 模型', status: 'completed', duration_ms: 1200, details: { case_execution_id: 'case_exec_1', turn_id: 'turn_1', attempt_id: 'attempt_1' } },
          { ordinal: 2, title: '执行交流潮流', status: 'failed', duration_ms: null, details: { case_execution_id: 'case_exec_1', turn_id: 'turn_2', attempt_id: 'attempt_2' } },
        ],
        actions: [{ action_id: 'retry_case_step', label: '重试此步骤', enabled: true }, { action_id: 'cancel_case', label: '停止案例', enabled: true }],
        disabled_reasons: ['运行被中断'],
      } },
    }
    const sendCommand = vi.fn().mockResolvedValue({ schema: 'capstone-command-receipt/1', command_id: 'cmd', idempotency_key: 'idem', thread_id: 'thr_case', run_id: 'run_case', status: 'accepted', accepted_event_seq: 13 })
    const transport: ThreadTransport = {
      connectionState: 'live', getSnapshot: async () => snapshot,
      getCatalog: async () => ({ schema: 'capstone-thread-catalog/1', models: [], profiles: [], cases: [] }),
      readEvents: async () => ({ schema: 'capstone-thread-events/1', thread_id: 'thr_case', after_event_seq: 12, next_event_seq: 12, has_more: false, events: [] }),
      sendCommand,
    }
    render(<ThreadFixtureApp client={new CapstoneThreadClient(transport)} threadId="thr_case" />)
    await screen.findByText('步骤 2 未完成')
    fireEvent.click(screen.getByRole('button', { name: '重试此步骤' }))
    await waitFor(() => expect(sendCommand).toHaveBeenCalled())
    expect(sendCommand.mock.calls[0][0]).toMatchObject({
      kind: 'retry_case_step', expected_event_seq: 12,
      payload: { case_execution_id: 'case_exec_1', step_ordinal: 2, failed_attempt_id: 'attempt_2' },
    })
  })

  it('preserves the composer draft and focus while Case progress updates', () => {
    const { rerender } = render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '保留这条草稿' } })
    input.focus()
    rerender(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} caseExecution={blockedCase} onCaseAction={vi.fn()} />)
    expect(input.value).toBe('保留这条草稿')
    expect(document.activeElement).toBe(input)
  })
})
