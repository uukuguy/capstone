import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { NetworkView } from './NetworkView'
import { sampleView } from './networkFixture'

afterEach(cleanup)

describe('operator network canvas', () => {
  it('shows provenance, partial numeric coverage, and neutral topology controls', () => {
    const view = { ...sampleView, overlay: {
      metric: 'loading_percent' as const, unit: '%' as const,
      source_ref: 'result:current', values: [{ id: 'line:11', value: 72.4 }],
    } }
    render(<NetworkView view={view} modelName="IEEE-39" focusKey="turn-1" />)
    expect(screen.getByRole('heading', { name: '电网视图' })).toBeTruthy()
    expect(screen.getByText(/模型结构 · gridctl/)).toBeTruthy()
    expect(screen.getByText('仅对 1 / 2 条有结果的线路着色')).toBeTruthy()
    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '适配全图' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '回到当前任务' })).toBeTruthy()
    expect(document.querySelector('.network-branch-label')?.textContent).toBe('Line 11')
  })

  it('allows manual zoom and returns focus when the step changes', () => {
    const { rerender } = render(<NetworkView view={sampleView} modelName="IEEE-39" focusKey="turn-1" />)
    const canvas = screen.getByRole('img', { name: '电网拓扑' })
    const initial = canvas.getAttribute('viewBox')
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    expect(canvas.getAttribute('viewBox')).not.toBe(initial)
    fireEvent.click(screen.getByRole('button', { name: '适配全图' }))
    expect(canvas.getAttribute('viewBox')).toBe('0 0 1000 600')
    rerender(<NetworkView view={sampleView} modelName="IEEE-39" focusKey="turn-2" />)
    expect(canvas.getAttribute('viewBox')).not.toBe('0 0 1000 600')
  })

  it('keeps a clear pending state before a current-run model opens', () => {
    render(<NetworkView view={null} modelName="IEEE-39" focusKey="pending" />)
    expect(screen.getByText('运行首步后显示登记模型拓扑')).toBeTruthy()
  })

  it('shows an unavailable state for an invalid or missing current-run projection', () => {
    render(<NetworkView view={null} modelName="IEEE-39" focusKey="missing" unavailable />)
    expect(screen.getByText('本轮电网视图暂不可用')).toBeTruthy()
  })

  it('focuses the next known task when execution starts', () => {
    const view = { ...sampleView, next_focus_ids: ['line:12'] }
    const { rerender } = render(<NetworkView view={view} modelName="IEEE-39" focusKey="ready" />)
    const canvas = screen.getByRole('img', { name: '电网拓扑' })
    const before = canvas.getAttribute('viewBox')
    rerender(<NetworkView view={view} modelName="IEEE-39" focusKey="executing" nextTask />)
    expect(canvas.getAttribute('viewBox')).not.toBe(before)
    expect(screen.getByText('正在对焦下一步已知目标')).toBeTruthy()
  })
})
