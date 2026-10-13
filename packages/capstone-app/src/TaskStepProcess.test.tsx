import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import TaskStepProcess from './TaskStepProcess'
afterEach(() => { cleanup(); localStorage.clear() })
describe('task step folding', () => {
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
    rerender(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2500 }]} storageKey="thread:attempt" running={false} renderTools={() => <span>01.1 GRID</span>} />)
    expect(details.open).toBe(false)
    expect(screen.getByText(/2.5s/)).toBeTruthy()
    details.open = true
    fireEvent(details, new Event('toggle'))
    unmount()
    const remounted = render(<TaskStepProcess steps={[{ ...step, status: 'completed', durationMs: 2500 }]} storageKey="thread:attempt" running={false} renderTools={() => <span>01.1 GRID</span>} />)
    expect(remounted.container.querySelector('details')!.open).toBe(true)
  })
})
