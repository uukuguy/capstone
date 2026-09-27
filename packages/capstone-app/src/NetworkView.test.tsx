import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { NetworkView } from './NetworkView'
import { sampleDiagramView, sampleView } from './networkFixture'

afterEach(cleanup)

describe('operator network canvas', () => {
  it('shows provenance, partial numeric coverage, and neutral topology controls', () => {
    const view = { ...sampleView, overlay: {
      metric: 'loading_percent' as const, unit: '%' as const,
      source_ref: 'result:current', values: [{ id: 'line:11', value: 72.4 }],
    } }
    render(<NetworkView view={view} modelName="IEEE-39" focusKey="turn-1" />)
    expect(screen.getByRole('heading', { name: '电网拓扑图' })).toBeTruthy()
    expect(screen.getByText('指令 1')).toBeTruthy()
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

  it('zooms by wheel only while Shift is held', () => {
    render(<NetworkView view={sampleView} modelName="IEEE-39" focusKey="turn-1" />)
    const canvas = screen.getByRole('img', { name: '电网拓扑' })
    const initial = canvas.getAttribute('viewBox')
    fireEvent.wheel(canvas, { deltaY: -100 })
    expect(canvas.getAttribute('viewBox')).toBe(initial)
    fireEvent.wheel(canvas, { deltaY: -100, shiftKey: true })
    expect(canvas.getAttribute('viewBox')).not.toBe(initial)
    expect(screen.getByText(/Shift \+ 滚轮缩放/)).toBeTruthy()
  })

  it('uses warm shades for all returned line loadings and darkest red for the highest', () => {
    const view = { ...sampleView, focus_ids: [], overlay: {
      metric: 'loading_percent' as const, unit: '%' as const, source_ref: 'result:current',
      values: [{ id: 'line:11', value: 42 }, { id: 'line:12', value: 73 }],
    } }
    render(<NetworkView view={view} modelName="IEEE-39" focusKey="turn-2" />)
    const lines = [...document.querySelectorAll('svg g')].filter((group) =>
      group.querySelector('title')?.textContent?.startsWith('Line '))
    const high = lines.find((group) => group.querySelector('title')?.textContent?.startsWith('Line 12'))
      ?.querySelectorAll('line')[1]?.getAttribute('stroke')
    const low = lines.find((group) => group.querySelector('title')?.textContent?.startsWith('Line 11'))
      ?.querySelectorAll('line')[1]?.getAttribute('stroke')
    const hue = (color: string | null | undefined) => Number(color?.match(/^hsl\((\d+) /)?.[1])
    expect(hue(low)).toBeLessThanOrEqual(18)
    expect(hue(high)).toBeLessThan(hue(low))
    expect(screen.getByText(/本轮相对色阶 42\.0–73\.0%/)).toBeTruthy()
  })

  it('keeps a clear pending state before a current-run model opens', () => {
    render(<NetworkView view={null} modelName="IEEE-39" focusKey="pending" />)
    expect(screen.getByText('正在读取案例电网…')).toBeTruthy()
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

  it('renders the authority geography with transformer symbols and only applicable legend keys', () => {
    render(<NetworkView view={sampleDiagramView} modelName="SciGRID" focusKey="turn-1" />)
    expect(screen.getByText(/3 母线 \/ 2 支路/)).toBeTruthy()
    expect(screen.getByText(/地理拓扑 · 模型坐标/)).toBeTruthy()
    expect(document.querySelectorAll('.network-transformer-symbol circle')).toHaveLength(2)
    expect(screen.getByText(/变压器/)).toBeTruthy()
    expect(screen.queryByText('直流连接')).toBeNull()
    expect(document.querySelector('.network-north')).toBeTruthy()
  })

  it('uses the muted run-indicator legend for a case preview without values', () => {
    render(<NetworkView view={null} previewDiagram={sampleDiagramView.diagram}
      modelName="SciGRID" focusKey="preview" />)
    expect(screen.getByText('运行指标')).toBeTruthy()
    expect(screen.getByText('执行后显示')).toBeTruthy()
    expect(screen.queryByText('案例底图 · 尚无运行数值')).toBeNull()
  })

  it('uses busbars for schematic buses and point markers for geographic buses', () => {
    const schematic = { ...sampleDiagramView, diagram: {
      ...sampleDiagramView.diagram, coordinate_system: 'schematic' as const,
    } }
    const { rerender } = render(<NetworkView view={schematic} modelName="IEEE-39" focusKey="turn-1" />)
    expect(document.querySelectorAll('.network-busbar')).toHaveLength(3)
    expect(document.querySelector('.legend-busbar')).toBeTruthy()
    rerender(<NetworkView view={sampleDiagramView} modelName="SciGRID" focusKey="turn-1" />)
    expect(document.querySelectorAll('.network-busbar')).toHaveLength(0)
    expect(document.querySelectorAll('.network-bus-point')).toHaveLength(3)
    expect(document.querySelector('.legend-bus-point')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '电气示意' }))
    expect(document.querySelectorAll('.network-busbar')).toHaveLength(3)
    expect(document.querySelector('.legend-busbar')).toBeTruthy()
    expect(screen.getByText('电气示意 · 拓扑生成')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '地理布局' }))
    expect(document.querySelectorAll('.network-bus-point')).toHaveLength(3)
  })

  it('preserves manual camera movement while the same diagram receives a neutral layer', () => {
    const { rerender } = render(<NetworkView view={sampleDiagramView} modelName="SciGRID" focusKey="turn-1" />)
    const canvas = screen.getByRole('img', { name: '电网拓扑' })
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    const manual = canvas.getAttribute('viewBox')
    rerender(<NetworkView view={{ ...sampleDiagramView }} modelName="SciGRID" focusKey="turn-1" />)
    expect(canvas.getAttribute('viewBox')).toBe(manual)
  })
})
