import { afterEach, describe, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import TaskStepProcess, { projectTaskSteps, toolExecutionMs } from './TaskStepProcess'
import { parseEventEnvelope } from './threadProtocol'
afterEach(() => { cleanup(); localStorage.clear(); vi.useRealTimers() })
describe('task step folding', () => {
  it('keeps long branch results bounded and renders their original Markdown only on demand', () => {
    const title = '核查区域差异'
    const text = '## 分支结论\n\n**已核实**：' + '两个区域的记录可按时间关联。'.repeat(30) + '\n\n## 计算口径\n\n- 使用 `interval_start` 关联\n- 缺失值不补零\n\n| 指标 | 数值 |\n| --- | --- |\n| 有效样本 | 12 |'
    const branch = { id: 'branch', parentStepId: 'analysis', title, questions: ['差异是什么？'], expectedOutputs: ['差异结论'], status: 'completed' as const, resultSummary: text, tools: [] }
    const step = { id: 'analysis', number: 1, title: '比较区域', status: 'completed' as const }
    const { container } = render(<TaskStepProcess steps={[step]} branches={[branch]} storageKey="result" running={false} renderTools={() => null} />)
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：比较区域' }))
    const toggle = screen.getByRole('button', { name: `查看详细结果：${title}` })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(container.querySelector('.capstone-result-excerpt')!.textContent!.length).toBeLessThanOrEqual(181)
    expect(screen.queryByRole('heading', { name: '计算口径' })).toBeNull()
    expect(screen.queryByRole('table')).toBeNull()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('heading', { name: '计算口径' })).toBeVisible()
    expect(screen.getByText('interval_start').tagName).toBe('CODE')
    expect(screen.getByRole('cell', { name: '有效样本' })).toBeVisible()
    fireEvent.click(toggle)
    expect(screen.queryByRole('table')).toBeNull()
  })
  it('keeps research metadata behind accessible compact controls while actual results remain visible', () => {
    const step = { id: 'research', number: 1, title: '核查差异', status: 'partial' as const,
      questions: ['差异从何而来'], expectedOutputs: ['差异表'], nextActionReason: '追加证据', derivedFrom: ['finding-one'], resultSummary: '部分查明' }
    render(<TaskStepProcess steps={[step]} storageKey="compact" running={false} renderTools={() => null} />)
    expect(screen.getByText('部分查明', { selector: '.capstone-process-step-preview span' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：核查差异' }))
    expect(screen.getByText('部分查明')).toBeVisible()
    expect(screen.queryByText('差异从何而来')).toBeNull()
    const button = screen.getByRole('button', { name: '研究问题' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(button)
    expect(screen.getByText('差异从何而来')).toBeVisible()
    fireEvent.click(button)
    expect(screen.queryByText('差异从何而来')).toBeNull()
  })
  it('defaults research details open in the reader and keeps tools folded independently', () => {
    const step = { id: 'research', number: 1, title: '核查差异', status: 'failed' as const, questions: ['差异从何而来'] }
    const { container } = render(<TaskStepProcess steps={[step]} storageKey="reader" running={false} expandedResearch renderTools={() => <p>工具记录</p>} />)
    expect(screen.getByText('差异从何而来')).toBeVisible()
    expect(container.querySelector<HTMLDetailsElement>('.capstone-business-step')!.open).toBe(false)
  })
  it('keeps evolving objective outcomes visible while tool details start folded', () => {
    const event = (seq: number, value: Record<string, unknown>) => parseEventEnvelope({
      event_id: `evt_${seq}`, event_seq: seq, event_type: 'runtime_event', event_version: 1,
      thread_id: 'thr_one', run_id: 'run_one', attempt_id: 'attempt_one', visibility: 'public',
      occurred_at: '2026-10-19T00:00:00Z', payload: { task_step: value },
    })
    const first = { id: 'compare', number: 1, title: '比较异常时段', status: 'running',
      questions: ['为什么两省变化不同？'], expected_outputs: ['可复核的差异表'], derived_from: ['finding-gap'] }
    const events = [event(1, first)]
    const { container, rerender } = render(<TaskStepProcess steps={projectTaskSteps(events, 'attempt_one')} storageKey="evolving" running renderTools={() => <p>真实工具明细</p>} />)
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：比较异常时段' }))
    fireEvent.click(screen.getByRole('button', { name: '研究问题' }))
    fireEvent.click(screen.getByRole('button', { name: '预期结果' }))
    expect(screen.getByText('为什么两省变化不同？')).toBeTruthy()
    expect(screen.getByText('可复核的差异表')).toBeTruthy()
    expect(container.querySelector<HTMLDetailsElement>('.capstone-business-step')!.open).toBe(false)
    events.push(event(2, { ...first, status: 'partial', result_summary: '差异已复核，原因尚未确定', next_action_reason: '需要核查检修窗口' }),
      event(3, { id: 'inspect', number: 2, title: '核查检修窗口', status: 'failed', result_summary: '资料未提供对应记录' }))
    rerender(<TaskStepProcess steps={projectTaskSteps(events, 'attempt_one')} storageKey="evolving" running={false} renderTools={() => null} />)
    expect(screen.getByText('差异已复核，原因尚未确定')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '下一步理由' }))
    expect(screen.getByText('需要核查检修窗口')).toBeTruthy()
    expect(screen.getByText('资料未提供对应记录', { selector: '.capstone-process-step-preview span' })).toBeVisible()
    expect(screen.getByText('· 部分完成')).toBeTruthy()
    expect(screen.getByText('· 失败')).toBeTruthy()
    expect(screen.getByRole('button', { name: '关联发现' })).toBeTruthy()
    expect(container.querySelectorAll('.capstone-business-step-record')).toHaveLength(2)
  })
  it('retains each explicit terminal outcome instead of dropping it or reporting success', () => {
    const outcomes = ['completed', 'partial', 'failed', 'limited', 'cancelled']
    const event = (seq: number, status: string, attemptId = 'attempt_one') => parseEventEnvelope({
      event_id: `event_${seq}`, event_seq: seq, event_type: 'runtime_action', event_version: 1,
      thread_id: 'thr_one', run_id: 'run_one', attempt_id: attemptId,
      occurred_at: '2026-10-19T00:00:00Z', visibility: 'public',
      payload: { task_step: { id: `step_${seq - 1}`, number: seq, title: `目标${seq - 1}`, status, duration_ms: 1200 } },
    })
    const initial = event(0, 'running')
    delete initial.payload.task_step
    initial.payload.task_steps = outcomes.map((_, index) => ({ id: `step_${index}`, number: index + 1, title: `目标${index}`, status: 'running' }))
    const events = outcomes.map((status, index) => event(index + 1, status))
    const steps = projectTaskSteps([initial, ...events, event(6, 'unknown'), event(7, 'completed', 'attempt_other')], 'attempt_one')
    expect(steps.map(step => step.status)).toEqual(outcomes)
    expect(steps.every(step => step.durationMs === 1200)).toBe(true)
    const { container } = render(<TaskStepProcess steps={steps} storageKey="outcomes" running renderTools={() => null} />)
    expect([...container.querySelectorAll('.capstone-step-heading')].map(summary => summary.textContent)).toEqual([
      expect.stringContaining('已完成'), expect.stringContaining('部分完成'), expect.stringContaining('失败'),
      expect.stringContaining('受限'), expect.stringContaining('已取消'),
    ])
    expect(container.textContent).not.toContain('执行中')
    expect(container.textContent).not.toContain('步骤未报告结束')
  })
  it('counts overlapping tool intervals once and leaves missing timing unknown', () => {
    expect(toolExecutionMs([{ startedAt: '2026-10-13T10:00:00Z', durationMs: 2000 }, { startedAt: '2026-10-13T10:00:01Z', durationMs: 2000 }])).toBe(3000)
    expect(toolExecutionMs([{ startedAt: '2026-10-13T10:00:00Z' }])).toBeUndefined()
  })
  it('shows response timing in the summary when a record exists', () => {
    const step = { id: 'recorded', number: 1, title: '检查', status: 'completed' as const, responseMs: 1700 };
    const { container } = render(<TaskStepProcess steps={[step]} storageKey="record" running={false} renderTools={() => <p>结果</p>} />)
    expect(container.querySelector('.capstone-step-heading')?.textContent).toContain('LLM 1.7s')
    expect(container.querySelector('.capstone-step-tools')?.textContent).not.toContain('模型')
  })
  it('states that step model timing was not recorded without inferring it from total or tool time', () => {
    const { container } = render(<TaskStepProcess steps={[{ id: 'historical', number: 1, title: '历史核查', status: 'completed', durationMs: 9000 }]} storageKey="missing-timing" running={false} toolCount={() => 1} toolMs={() => 1000} renderTools={() => null} />)
    expect(screen.getByText('· LLM 未记录')).toHaveAttribute('title', '宿主未保存步骤模型响应耗时')
    expect(container.querySelector('.capstone-step-heading')?.textContent).not.toContain('LLM 8.0s')
  })
  it('counts live time and keeps the recorded duration after completion', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-13T10:00:02Z'))
    const step = { id: 'runtime-1', number: 1, title: '组织执行', status: 'running' as const, startedAt: '2026-10-13T10:00:00Z' }
    const { rerender } = render(<TaskStepProcess steps={[step]} storageKey="timer" running renderTools={() => null} />)
    expect(screen.getByText('2.0s · 执行中')).toBeTruthy()
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByText('3.0s · 执行中')).toBeTruthy()
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2800, responseMs: 1700 }]} storageKey="timer" running={false} renderTools={() => null} />)
    act(() => vi.advanceTimersByTime(2000))
    expect(screen.getByText('2.8s')).toBeTruthy()
    expect(screen.getByText('· 已完成')).toBeTruthy()
    expect(screen.getByText('· LLM 1.7s')).toBeTruthy()
  })
  it('shows the number of tools inside a collapsed step', () => {
    render(<TaskStepProcess steps={[{ id: 'solve', number: 1, title: '求解', status: 'running' }]} storageKey="count" running={false} toolCount={() => 5} renderTools={() => <span>GRID</span>} />)
    expect(screen.getByText('· 工具 5次')).toBeTruthy()
    expect(screen.getByText('任务已结束 · 步骤未报告结束')).toBeTruthy()
  })
  it('updates the parent tool total as branch tools arrive without claiming complete model timing', () => {
    const props = { steps: [{ id: 'review', number: 1, title: '核验', status: 'running' as const, responseMs: 1700 }], storageKey: 'branch-totals', running: true, toolCount: () => 1, renderTools: () => null }
    const branch = { id: 'child', parentStepId: 'review', title: '指标', questions: [], expectedOutputs: [], status: 'running' as const, tools: [{ id: 't1', name: 'bash', status: 'completed' as const }] }
    const { container, rerender } = render(<TaskStepProcess {...props} branches={[branch]} />)
    expect(container.querySelector('.capstone-step-heading')?.textContent).toContain('工具 2次')
    expect(container.querySelector('.capstone-step-heading')?.textContent).toContain('主流程 LLM 1.7s')
    rerender(<TaskStepProcess {...props} branches={[{ ...branch, responses: { '1': 2500, '2': 1500 }, tools: [...branch.tools, { id: 't2', name: 'read', status: 'running' }] }]} />)
    expect(container.querySelector('.capstone-step-heading')?.textContent).toContain('工具 3次')
    expect(container.querySelector('.capstone-step-heading')?.textContent).toContain('分支 LLM 2次/4.0s')
  })
  it('defaults tools folded and retains an explicit open choice through reload', () => {
    const step = { id: 'inspect', number: 1, title: '检查拓扑', status: 'running' as const }
    const { container, rerender, unmount } = render(<TaskStepProcess steps={[step]} storageKey="thread:attempt" running renderTools={() => <span>01.1 GRID</span>} />)
    const details = container.querySelector('details')!
    expect(details.open).toBe(false)
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2500 }, { id: 'solve', number: 2, title: '计算', status: 'completed', durationMs: 1000 }]} storageKey="thread:attempt" running={false} renderTools={() => <span>GRID</span>} />)
    expect(details.open).toBe(false)
    expect(container.querySelectorAll('details')[1].open).toBe(false)
    expect(screen.getByText(/2.5s/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：检查拓扑' }))
    expect(localStorage.getItem('capstone-step-open:thread:attempt:inspect')).toBe('true')
    unmount()
    const remounted = render(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2500 }]} storageKey="thread:attempt" running={false} renderTools={() => <span>01.1 GRID</span>} />)
    expect(remounted.getByRole('button', { name: '折叠步骤：检查拓扑' })).toHaveAttribute('aria-expanded', 'true')
  })
  it('retains a manually closed last step after completion and reload', () => {
    localStorage.setItem('capstone-step-open:manual:solve', 'true')
    const step = { id: 'solve', number: 1, title: '求解', status: 'running' as const }
    const { container, rerender, unmount } = render(<TaskStepProcess steps={[step]} storageKey="manual" running renderTools={() => null} />)
    const details = container.querySelector('details')!
    fireEvent.click(screen.getByRole('button', { name: '折叠步骤：求解' }))
    expect(localStorage.getItem('capstone-step-open:manual:solve')).toBe('false')
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed' }]} storageKey="manual" running={false} renderTools={() => null} />)
    expect(details.open).toBe(false)
    unmount()
    const reloaded = render(<TaskStepProcess steps={[{ ...step, status: 'completed' }]} storageKey="manual" running={false} renderTools={() => null} />)
    expect(reloaded.container.querySelector('details')!.open).toBe(false)
  })
  it('defaults completed tools folded when steps render separately', () => {
    const { container } = render(<TaskStepProcess steps={[{ id: 'first', number: 1, title: '检查', status: 'completed' }]} storageKey="separate" running={false} renderTools={() => null} />)
    expect(container.querySelector('details')!.open).toBe(false)
  })
})
