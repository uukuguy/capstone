import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { NetworkView } from './NetworkView'
import ThreadModelPane, { projectActiveNetworkView } from './ThreadModelPane'
import { parseThreadSnapshot } from './threadProtocol'
import { threadUiFixture } from './threadUiFixtures'
import { sampleDiagramView, sampleView } from './networkFixture'

afterEach(cleanup)

describe('operator network canvas', () => {
  it('restores admitted full-result colors for a selected historical instruction', () => {
    const view = structuredClone(sampleDiagramView)
    view.layer.focus_ids = []
    const snapshot = parseThreadSnapshot(threadUiFixture('idle-ieee39').snapshot)
    const context = { ...snapshot.activeModelContext, id: 'ctx_old', modelId: view.diagram.model.id,
      modelRevision: view.diagram.model.revision, implementationFamily: 'pypsa' }
    const resultProjection = { modelId: context.modelId, modelRevision: context.modelRevision,
      overlay: { metric: 'loading_percent', unit: '%', sourceRef: 'result:old', values: [{ elementId: 'line:1', value: 25 }] },
    } as Parameters<typeof projectActiveNetworkView>[1]
    render(<ThreadModelPane snapshot={snapshot} activePage={snapshot.activeGridPageId} viewedPage="page_old"
      gridPages={[{ pageId: 'page_old', context, networkView: view }]} isHistorical projectionEventSeq={10}
      previewDiagram={null} modelOptions={[]}
      onSelectPage={() => {}} resultProjection={resultProjection} viewingInstruction />)
    expect(document.querySelector('svg title')?.textContent).toContain('25.0')
  })
  it('shows the selected instruction number while preserving the layer ordinal', () => {
    render(<NetworkView view={sampleView} modelName="IEEE-39" focusKey="attempt_4" instructionLabel="指令 4" />)
    expect(screen.getByText('指令 4')).toBeTruthy()
    expect(screen.queryByText('指令 1')).toBeNull()
  })
  it('preserves the current task subset overlay over a previous full result', () => {
    const view = structuredClone(sampleDiagramView)
    view.layer.focus_ids = ['line:1']
    view.layer.overlay = { metric: 'loading_percent', unit: '%', source_ref: 'result:task', values: [{ id: 'line:1', value: 42 }] }
    const projection = { modelId: view.diagram.model.id, modelRevision: view.diagram.model.revision,
      overlay: { metric: 'loading_percent', unit: '%', sourceRef: 'result:full', values: view.diagram.branches.map((branch) => ({ elementId: branch.id, value: 90 })) },
    } as Parameters<typeof projectActiveNetworkView>[1]
    const taskView = projectActiveNetworkView(view, projection, undefined)
    expect(taskView.layer.overlay).toEqual(view.layer.overlay)
    const selectedResultView = projectActiveNetworkView(view, projection, 'line:1')
    expect(selectedResultView.layer.overlay?.source_ref).toBe('result:full')
    view.layer.overlay = null
    expect(projectActiveNetworkView(view, projection, undefined).layer.overlay).toBeNull()
  })

  it('shows provenance, partial numeric coverage, and neutral topology controls', () => {
    const view = { ...sampleView, overlay: {
      metric: 'loading_percent' as const, unit: '%' as const,
      source_ref: 'result:current', values: [{ id: 'line:11', value: 72.4 }],
    } }
    render(<NetworkView view={view} modelName="IEEE-39" focusKey="turn-1" />)
    expect(screen.getByRole('heading', { name: '电气拓扑图' })).toBeTruthy()
    expect(screen.getByText('指令 1')).toBeTruthy()
    expect(screen.getByText(/模型来源 · gridctl/)).toBeTruthy()
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

  it.each([
    ['diagram_limit', '超过当前视图容量'],
    ['projection_source_unavailable', '电网服务未能返回'],
    ['projection_model_mismatch', '模型或版本不一致'],
    ['projection_invalid', '未通过数据校验'],
  ])('shows a specific cause and recovery action for %s', (code, copy) => {
    render(<NetworkView view={null} modelName="Grid" focusKey="failed" unavailable failureCode={code} />)
    expect(screen.getByRole('alert').textContent).toContain(copy)
    expect(screen.getByText(`诊断代码：${code}`)).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toMatch(/请选择|请从|请重试/)
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

  it('uses electrical busbars while preserving geographic diagram coordinates', () => {
    const schematic = { ...sampleDiagramView, diagram: {
      ...sampleDiagramView.diagram, coordinate_system: 'schematic' as const,
    } }
    const { rerender } = render(<NetworkView view={schematic} modelName="IEEE-39" focusKey="turn-1" />)
    expect(document.querySelectorAll('.network-busbar')).toHaveLength(3)
    expect(document.querySelector('.legend-busbar')).toBeTruthy()
    rerender(<NetworkView view={sampleDiagramView} modelName="SciGRID" focusKey="turn-1" />)
    expect(document.querySelectorAll('.network-busbar')).toHaveLength(3)
    expect(document.querySelector('.legend-busbar')).toBeTruthy()
    expect(document.querySelector('.network-north')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '电气示意' })).toBeNull()
  })

  it('preserves manual camera movement while the same diagram receives a neutral layer', () => {
    const { rerender } = render(<NetworkView view={sampleDiagramView} modelName="SciGRID" focusKey="turn-1" />)
    const canvas = screen.getByRole('img', { name: '电网拓扑' })
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    const manual = canvas.getAttribute('viewBox')
    rerender(<NetworkView view={{ ...sampleDiagramView }} modelName="SciGRID" focusKey="turn-1" />)
    expect(canvas.getAttribute('viewBox')).toBe(manual)
  })

  it('keeps the dynamic diagram visible when a requested focus is not a diagram element', () => {
    const safeView = projectActiveNetworkView(sampleDiagramView, undefined, 'missing-element')
    render(<NetworkView view={safeView} modelName="SciGRID" focusKey="safe-focus" />)

    expect(screen.getByRole('img', { name: '电网拓扑' })).toBeTruthy()
    expect(screen.getByText(/3 母线 \/ 2 支路/)).toBeTruthy()
  })
})
