import { StrictMode } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { NetworkView } from './NetworkView'
import ThreadModelPane, { projectActiveNetworkView } from './ThreadModelPane'
import { parseThreadSnapshot } from './threadProtocol'
import { threadUiFixture } from './threadUiFixtures'
import { sampleDiagramView, sampleView } from './networkFixture'
import { threadPreviewDiagram } from './threadModelDiagram'

afterEach(() => { cleanup(); sessionStorage.clear() })

describe('operator network canvas', () => {
  it('restores the exact camera after switching model views and remounting', () => {
    const canvas = (key: string) => <NetworkView key={key} view={sampleDiagramView} modelName={key}
      focusKey={key} cameraStorageKey="camera-test" cameraViewKey={key} />
    const mounted = render(canvas('model-a'))
    fireEvent.click(screen.getByRole('button', { name: '放大' }))
    const saved = screen.getByRole('img', { name: '电网拓扑' }).getAttribute('viewBox')
    mounted.rerender(canvas('model-b'))
    expect(screen.getByRole('img', { name: '电网拓扑' }).getAttribute('viewBox')).not.toBe(saved)
    mounted.rerender(canvas('model-a'))
    expect(screen.getByRole('img', { name: '电网拓扑' }).getAttribute('viewBox')).toBe(saved)
    mounted.rerender(<NetworkView key="model-a" view={{ ...sampleDiagramView, ordinal: 2 }} modelName="model-a"
      focusKey="model-a" cameraStorageKey="camera-test" cameraViewKey="model-a" />)
    expect(screen.getByRole('img', { name: '电网拓扑' }).getAttribute('viewBox')).toBe(saved)
    mounted.unmount()
    render(<StrictMode>{canvas('model-a')}</StrictMode>)
    expect(screen.getByRole('img', { name: '电网拓扑' }).getAttribute('viewBox')).toBe(saved)
  })

  it.each(['gridctl', 'pypsamodelctl'])('renders model names without renumbering for %s', (source) => {
    const view = structuredClone(sampleDiagramView)
    view.diagram.model.source = source
    view.diagram.coordinate_system = 'schematic'
    view.diagram.buses = [
      { id: '10', label: '11', x: 0, y: 0, vn_kv: 110 },
      { id: '12', label: '13', x: 1, y: 1, vn_kv: 110 },
    ]
    view.diagram.branches = [{ id: 'line:0', kind: 'line', label: '11–13 circuit A', from_bus: '10', to_bus: '12' }]
    view.layer.focus_ids = ['line:0']
    render(<NetworkView view={view} modelName="Model" focusKey="names" />)
    expect(Array.from(document.querySelectorAll('.network-node-label'), (node) => node.textContent)).toEqual(['bus 11', 'bus 13'])
    expect(document.querySelector('.network-branch-label')?.textContent).toBe('line 11–13 circuit A')
    expect(Array.from(document.querySelectorAll('svg title'), (node) => node.textContent)).toContain('line 11–13 circuit A')
    fireEvent.mouseEnter(document.querySelector('.network-busbar')!.parentElement!)
    expect(document.querySelector('.network-hover-id')?.textContent).toBe('bus 11')
    fireEvent.mouseEnter(document.querySelector('.network-branch-label')!.parentElement!)
    expect(document.querySelector('.network-hover-id')?.textContent).toBe('line 11–13 circuit A')
  })

  it.each([
    ['line', '17', 'line 17'],
    ['trafo', '0', 'trafo 0'],
    ['trafo3w', '15', 'trafo 15'],
    ['transformer', 'T13-central', 'trafo T13-central'],
    ['link', 'electrolyser-0', 'link electrolyser-0'],
    ['line', 'Line 17', 'line 17'],
    ['line', 'line 17', 'line 17'],
    ['transformer', 'Transformer T13-central', 'trafo T13-central'],
    ['trafo3w', 'Trafo3W 15', 'trafo 15'],
  ] as const)('shows the component type for %s named %s', (kind, name, expected) => {
    const view = structuredClone(sampleDiagramView)
    view.diagram.buses[0].label = 'Bus DE0'
    view.diagram.branches[0].kind = kind
    view.diagram.branches[0].label = name
    render(<NetworkView view={view} modelName="Model" focusKey="type-labels" />)
    expect(document.querySelector('.network-branch-label')?.textContent).toBe(expected)
    expect(Array.from(document.querySelectorAll('.network-node-label'), (node) => node.textContent)).toContain('bus DE0')
    expect(Array.from(document.querySelectorAll('svg title'), (node) => node.textContent)).toContain(expected)
  })

  it('keeps the recorded IEEE39 preview aligned with registered bus names', () => {
    expect(threadPreviewDiagram.buses.find((bus) => bus.id === '10')?.label).toBe('11')
    expect(threadPreviewDiagram.buses.find((bus) => bus.id === '12')?.label).toBe('13')
  })

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
    expect(document.querySelector('.network-branch-label')?.textContent).toBe('line 11')
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
      group.querySelector('title')?.textContent?.startsWith('line '))
    const high = lines.find((group) => group.querySelector('title')?.textContent?.startsWith('line 12'))
      ?.querySelectorAll('line')[1]?.getAttribute('stroke')
    const low = lines.find((group) => group.querySelector('title')?.textContent?.startsWith('line 11'))
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
