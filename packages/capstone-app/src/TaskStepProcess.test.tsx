import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import TaskStepProcess from './TaskStepProcess'
afterEach(() => { cleanup(); localStorage.clear(); vi.useRealTimers() })
describe('task step folding', () => {
  it('counts live time and keeps the recorded duration after completion', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-13T10:00:02Z'))
    const step = { id: 'runtime-1', number: 1, title: '组织执行', status: 'running' as const, startedAt: '2026-10-13T10:00:00Z' }
    const { rerender } = render(<TaskStepProcess steps={[step]} storageKey="timer" running renderTools={() => null} />)
    expect(screen.getByText('执行中 · 2.0s')).toBeTruthy()
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByText('执行中 · 3.0s')).toBeTruthy()
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2800, responseMs: 1700 }]} storageKey="timer" running={false} renderTools={() => null} />)
    act(() => vi.advanceTimersByTime(2000))
    expect(screen.getByText('已结束 · 2.8s · 模型响应 1.7s')).toBeTruthy()
  })
  it('shows the number of tools inside a collapsed step', () => {
    render(<TaskStepProcess steps={[{ id: 'solve', number: 1, title: '求解', status: 'running' }]} storageKey="count" running={false} toolCount={() => 5} renderTools={() => <span>GRID</span>} />)
    expect(screen.getByText('5 次工具调用')).toBeTruthy()
    expect(screen.getByText('任务已结束 · 步骤未报告结束')).toBeTruthy()
  })
  it('starts open, collapses completed steps and retains a manual choice through reload', () => {
    const step = { id: 'inspect', number: 1, title: '检查拓扑', status: 'running' as const }
    const { container, rerender, unmount } = render(<TaskStepProcess steps={[step]} storageKey="thread:attempt" running renderTools={() => <span>01.1 GRID</span>} />)
    const details = container.querySelector('details')!
    expect(details.open).toBe(true)
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2500 }, { id: 'solve', number: 2, title: '计算', status: 'completed', durationMs: 1000 }]} storageKey="thread:attempt" running={false} renderTools={() => <span>GRID</span>} />)
    expect(details.open).toBe(false)
    expect(container.querySelectorAll('details')[1].open).toBe(true)
    expect(screen.getByText(/2.5s/)).toBeTruthy()
    details.open = true
    fireEvent(details, new Event('toggle'))
    unmount()
    const remounted = render(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2500 }]} storageKey="thread:attempt" running={false} renderTools={() => <span>01.1 GRID</span>} />)
    expect(remounted.container.querySelector('details')!.open).toBe(true)
  })
  it('retains a manually closed last step after completion and reload', () => {
    const step = { id: 'solve', number: 1, title: '求解', status: 'running' as const }
    const { container, rerender, unmount } = render(<TaskStepProcess steps={[step]} storageKey="manual" running renderTools={() => null} />)
    const details = container.querySelector('details')!
    details.open = false
    fireEvent(details, new Event('toggle'))
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed' }]} storageKey="manual" running={false} renderTools={() => null} />)
    expect(details.open).toBe(false)
    unmount()
    const reloaded = render(<TaskStepProcess steps={[{ ...step, status: 'completed' }]} storageKey="manual" running={false} renderTools={() => null} />)
    expect(reloaded.container.querySelector('details')!.open).toBe(false)
  })
  it('uses the final step of the whole process when steps render separately', () => {
    const { container } = render(<TaskStepProcess steps={[{ id: 'first', number: 1, title: '检查', status: 'completed' }]} lastStepId="last" storageKey="separate" running={false} renderTools={() => null} />)
    expect(container.querySelector('details')!.open).toBe(false)
  })
})
