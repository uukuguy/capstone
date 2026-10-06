import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent, WheelEvent } from 'react'
import { Crosshair, Maximize2, Minus, Plus } from 'lucide-react'
import { layoutNetwork, usesModelCoordinates } from './networkLayout'
import type { PositionedBus } from './networkLayout'
import type { LegacyNetworkView, NetworkDiagram, NetworkView as NetworkViewData } from './types'

type Camera = { x: number; y: number; width: number; height: number }
const FULL: Camera = { x: 0, y: 0, width: 1000, height: 600 }

const ELEMENT_PREFIX = {
  bus: 'bus', line: 'line', link: 'link', transformer: 'trafo',
  trafo: 'trafo', trafo3w: 'trafo',
} as const

function elementLabel(kind: keyof typeof ELEMENT_PREFIX, name: string): string {
  const prefix = ELEMENT_PREFIX[kind]
  const lowerName = name.toLowerCase()
  const existingPrefix = [prefix, kind].find((candidate) =>
    lowerName === candidate || lowerName.startsWith(`${candidate} `))
  return existingPrefix ? `${prefix}${name.slice(existingPrefix.length)}` : `${prefix} ${name}`
}

function taskCamera(view: LegacyNetworkView | NetworkDiagram, buses: PositionedBus[], focusIds: string[]): Camera {
  const byId = new Map(buses.map((bus) => [bus.id, bus]))
  const branchById = new Map(view.branches.map((branch) => [branch.id, branch]))
  const points = focusIds.flatMap((id) => {
    const bus = byId.get(id)
    if (bus) return [bus]
    const branch = branchById.get(id)
    if (!branch) return []
    return [byId.get(branch.from_bus), byId.get(branch.to_bus)]
      .filter((value): value is PositionedBus => value !== undefined)
  })
  if (!points.length) return FULL
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const centerX = (Math.min(...xs) + Math.max(...xs)) / 2
  const centerY = (Math.min(...ys) + Math.max(...ys)) / 2
  const width = Math.min(950, Math.max(380,
    Math.max(...xs) - Math.min(...xs) + 250,
    (Math.max(...ys) - Math.min(...ys) + 170) * 5 / 3))
  const height = width * 0.6
  return { x: centerX - width / 2, y: centerY - height / 2, width, height }
}

function valueColor(metric: 'loading_percent' | 'voltage_pu', value: number,
                    loadingRange: { min: number; max: number } | null): string {
  if (metric === 'voltage_pu') {
    const deviation = Math.min(1, Math.abs(value - 1) / 0.15)
    return `hsl(${Math.round(178 - deviation * 160)} 65% 39%)`
  }
  const relative = loadingRange?.max === loadingRange?.min ? 1
    : loadingRange ? (value - loadingRange.min) / (loadingRange.max - loadingRange.min) : 0
  const intensity = Math.min(1, Math.max(0, relative))
  return `hsl(${Math.round(14 - intensity * 10)} 68% ${Math.round(54 - intensity * 16)}%)`
}

export function NetworkView({ view, previewDiagram = null, modelName, focusKey, instructionLabel, compact = false,
                              nextTask = false, unavailable = false,
                              previewUnavailable = false, failureCode, historyFocusIds = [] }: {
  view: NetworkViewData | null; previewDiagram?: NetworkDiagram | null;
  modelName: string; focusKey: string
  instructionLabel?: string
  compact?: boolean
  nextTask?: boolean;
  unavailable?: boolean; previewUnavailable?: boolean
  failureCode?: string
  historyFocusIds?: string[]
}) {
  const [camera, setCamera] = useState<Camera>(FULL)
  const [hovered, setHovered] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; camera: Camera } | null>(null)
  const geometry = view?.schema === 'capstone-network-view/2.0' ? view.diagram : view || previewDiagram
  const layer = view?.schema === 'capstone-network-view/2.0' ? view.layer : view
  const viewIdentity = view?.schema === 'capstone-network-view/2.0'
    ? `${view.diagram.ref}:${view.ordinal}:${view.layer.focus_ids.join(',')}:${view.layer.next_focus_ids.join(',')}`
    : view ? `${view.model.revision}:${view.ordinal}:${view.focus_ids.join(',')}:${view.next_focus_ids.join(',')}`
      : previewDiagram?.ref || 'empty'
  const nativeSchematic = geometry?.schema === 'capstone-network-diagram/1.0'
    ? geometry.coordinate_system === 'schematic' : geometry?.coordinate_status === 'schematic-required'
  const nodes = useMemo(() => geometry ? layoutNetwork(geometry) : [], [geometry])
  const modelCoordinates = useMemo(() => geometry ? usesModelCoordinates(geometry) : false, [geometry])
  const byId = useMemo(() => new Map(nodes.map((bus) => [bus.id, bus])), [nodes])
  const values = useMemo(() => new Map(layer?.overlay?.values.map((item) => [item.id, item.value]) || []), [layer])
  const loadingRange = useMemo(() => {
    if (layer?.overlay?.metric !== 'loading_percent' || !geometry) return null
    const lineIds = new Set(geometry.branches.filter((branch) => branch.kind === 'line').map((branch) => branch.id))
    const observed = layer.overlay.values.filter((item) => lineIds.has(item.id)).map((item) => item.value)
    return observed.length ? { min: Math.min(...observed), max: Math.max(...observed) } : null
  }, [geometry, layer])
  const focusIds = useMemo(() => layer ? nextTask ? layer.next_focus_ids : layer.focus_ids : [], [layer, nextTask])
  const historyIds = useMemo(() => new Set(historyFocusIds), [historyFocusIds])
  const focusBuses = useMemo(() => new Set(geometry?.branches.filter((branch) =>
    focusIds.includes(branch.id)).flatMap((branch) => [branch.from_bus, branch.to_bus]) || []), [geometry, focusIds])

  useEffect(() => {
    setCamera(geometry ? taskCamera(geometry, nodes, focusIds) : FULL)
    // Focus changes on step/execution transitions or on arrival of a different diagram.
  }, [focusKey, viewIdentity])

  function zoom(factor: number, clientX?: number, clientY?: number, target?: SVGSVGElement) {
    setCamera((before) => {
      const width = Math.max(120, Math.min(1500, before.width * factor))
      const height = width * 0.6
      const rect = target?.getBoundingClientRect()
      const relativeX = rect && rect.width > 0 && clientX !== undefined
        ? Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)) : 0.5
      const relativeY = rect && rect.height > 0 && clientY !== undefined
        ? Math.min(1, Math.max(0, (clientY - rect.top) / rect.height)) : 0.5
      return { x: before.x + (before.width - width) * relativeX,
        y: before.y + (before.height - height) * relativeY, width, height }
    })
  }

  function onWheel(event: WheelEvent<SVGSVGElement>) {
    if (!event.shiftKey) return
    event.preventDefault()
    zoom(event.deltaY > 0 ? 1.13 : 0.88, event.clientX, event.clientY, event.currentTarget)
  }

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    drag.current = { x: event.clientX, y: event.clientY, camera }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!drag.current) return
    const rect = event.currentTarget.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const origin = drag.current
    setCamera({ ...origin.camera,
      x: origin.camera.x - (event.clientX - origin.x) * origin.camera.width / rect.width,
      y: origin.camera.y - (event.clientY - origin.y) * origin.camera.height / rect.height })
  }

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === '+' || event.key === '=') zoom(0.8)
    else if (event.key === '-') zoom(1.25)
    else if (event.key.startsWith('Arrow')) {
      const step = camera.width * 0.07
      setCamera((before) => ({ ...before,
        x: before.x + (event.key === 'ArrowRight' ? step : event.key === 'ArrowLeft' ? -step : 0),
        y: before.y + (event.key === 'ArrowDown' ? step : event.key === 'ArrowUp' ? -step : 0) }))
    } else return
    event.preventDefault()
  }

  const colored = layer?.overlay?.values.length || 0
  const hoveredValue = hovered === null ? undefined : values.get(hovered)
  const denominator = layer?.overlay?.metric === 'voltage_pu'
    ? geometry?.buses.length || 0 : geometry?.branches.filter((branch) => branch.kind === 'line').length || 0
  const dense = nodes.length > 100
  // Registered diagram views keep their authority coordinates, while using
  // the electrical busbar glyph in the legend and on the map. Legacy views
  // without diagram semantics retain their point markers.
  const schematic = Boolean(nativeSchematic || geometry?.schema === 'capstone-network-diagram/1.0')
  // Keep strokes, symbols, and labels readable in screen pixels while the SVG
  // viewBox zooms into a dense network.
  const visualScale = Math.max(0.12, Math.min(1.25, camera.width / FULL.width))
  // Electrical symbols need a slightly larger floor than connecting lines so
  // buses and transformers remain identifiable in a focused network region.
  const symbolScale = Math.max(visualScale, Math.min(0.6, Math.max(0.3, camera.width / 650)))
  const branchKinds = new Set(geometry?.branches.map((branch) => branch.kind) || [])
  const toolbar = <div className="network-toolbar" aria-label="电网图操作">
    <button type="button" onClick={() => zoom(0.8)} aria-label="放大" title="放大">{compact ? <Plus aria-hidden="true" /> : '＋'}</button>
    <button type="button" onClick={() => zoom(1.25)} aria-label="缩小" title="缩小">{compact ? <Minus aria-hidden="true" /> : '－'}</button>
    {!compact && <span className="network-toolbar-divider" />}
    <button type="button" onClick={() => setCamera(FULL)} aria-label="适配全图" title="适配全图">{compact ? <Maximize2 aria-hidden="true" /> : '适配全图'}</button>
    <button type="button" onClick={() => setCamera(taskCamera(geometry!, nodes, focusIds))} aria-label="回到当前任务" title="回到当前任务">{compact ? <Crosshair aria-hidden="true" /> : '回到当前任务'}</button>
  </div>
  return <section className={`network-card${compact ? ' is-compact' : ''}`} aria-labelledby="network-title">
    <div className="network-head"><div>{!compact && <span className="eyebrow">TOPOLOGY / VIEW</span>}
      <h2 id="network-title">电气拓扑图</h2></div><div className="network-head-context">
        {view && <span className="network-step">{instructionLabel || `指令 ${view.ordinal}`}</span>}
        <span className="network-model">{modelName}</span></div></div>
    {geometry ? <>
      <div className={compact ? 'network-control-row' : undefined}>
      <div className="network-meta"><span>{compact ? '' : '模型来源 · '}{geometry!.model.source} · {geometry!.buses.length} 母线 / {geometry!.branches.length} 支路</span>
        <span>{geometry!.schema === 'capstone-network-diagram/1.0'
          ? geometry!.coordinate_system === 'geographic' ? '地理拓扑 · 模型坐标' : modelCoordinates ? '电气示意 · 模型坐标' : '电气示意布局'
          : modelCoordinates ? '模型坐标 · 未经地理校验'
            : geometry!.coordinate_status === 'provided-unverified' ? '示意布局 · 模型坐标过密' : '示意布局'}</span></div>
      {toolbar}
      </div>
      {nextTask && <div className="network-focus-status">{focusIds.length
        ? '正在对焦下一步已知目标' : '下一步暂无可定位元件，显示全图范围'}</div>}
      <div className="network-canvas-frame">
        <svg role="img" aria-label="电网拓扑" tabIndex={0}
          viewBox={`${camera.x} ${camera.y} ${camera.width} ${camera.height}`}
          onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
          onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}
          onKeyDown={onKeyDown}>
          <defs><pattern id="network-grid" width="36" height="36" patternUnits="userSpaceOnUse">
            <path d="M 36 0 L 0 0 0 36" fill="none" stroke="#edf1ef" strokeWidth="1" />
          </pattern></defs>
          <rect x="-500" y="-300" width="2000" height="1200" fill="white" />
          <rect x="-500" y="-300" width="2000" height="1200" fill="url(#network-grid)" />
          {geometry!.branches.map((branch) => {
            const from = byId.get(branch.from_bus), to = byId.get(branch.to_bus)
            if (!from || !to) return null
            const label = elementLabel(branch.kind, branch.label)
            const value = values.get(branch.id)
            const highlighted = focusIds.includes(branch.id)
            const historical = !highlighted && historyIds.has(branch.id)
            const color = value === undefined ? highlighted ? '#187b78' :
              historical ? '#91aaa6' : branch.kind === 'link' ? '#718ca0' : '#829c98'
              : valueColor(layer!.overlay!.metric, value, loadingRange)
            const transformer = ['transformer', 'trafo', 'trafo3w'].includes(branch.kind)
            const centerX = (from.x + to.x) / 2, centerY = (from.y + to.y) / 2
            return <g key={branch.id} onMouseEnter={() => setHovered(branch.id)}
              onMouseLeave={() => setHovered(null)}>
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke="transparent" strokeWidth={Math.max(4, (dense ? 7 : 20) * visualScale)} />
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={color} strokeWidth={(highlighted ? dense ? 3 : 6 : historical ? dense ? 2 : 3.5 : dense ? 1.5 : value === undefined ? 2.5 : 4) * visualScale}
                strokeDasharray={branch.kind === 'link' ? '9 6' : undefined}
                strokeLinecap="round" />
              {transformer && <g className="network-transformer-symbol" aria-hidden="true">
                <circle cx={centerX - (dense ? 2.3 : 4) * symbolScale} cy={centerY}
                  r={(dense ? 2.7 : 4.5) * symbolScale}
                  style={{ strokeWidth: `${1.2 * visualScale}px` }} />
                <circle cx={centerX + (dense ? 2.3 : 4) * symbolScale} cy={centerY}
                  r={(dense ? 2.7 : 4.5) * symbolScale}
                  style={{ strokeWidth: `${1.2 * visualScale}px` }} />
              </g>}
              {highlighted && <text x={centerX + 7 * visualScale} y={centerY - 9 * visualScale}
                className="network-branch-label"
                style={{ fontSize: `${12 * visualScale}px`, strokeWidth: `${4 * visualScale}px`,
                  ...(value === undefined ? {} : { fill: color }) }}>{label}</text>}
              <title>{label}{value === undefined ? '' : ` · ${value.toFixed(1)} ${layer!.overlay!.unit}`}</title>
            </g>
          })}
          {nodes.map((bus) => {
            const label = elementLabel('bus', bus.label)
            const value = values.get(bus.id)
            const highlighted = focusIds.includes(bus.id)
            const historical = !highlighted && historyIds.has(bus.id)
            return <g key={bus.id} onMouseEnter={() => setHovered(bus.id)}
              onMouseLeave={() => setHovered(null)}>
              {schematic ? <line className="network-busbar"
                x1={bus.x - (highlighted ? 11 : 8) * symbolScale} x2={bus.x + (highlighted ? 11 : 8) * symbolScale}
                y1={bus.y} y2={bus.y}
                stroke={value === undefined ? highlighted ? '#0d7771' : historical ? '#91aaa6' : '#344c53'
                  : valueColor(layer!.overlay!.metric, value, loadingRange)}
                strokeWidth={(highlighted ? 5 : 3.5) * visualScale} strokeLinecap="square" />
                : <circle className="network-bus-point" cx={bus.x} cy={bus.y}
                  r={(highlighted ? dense ? 5 : 9 : dense ? 2.9 : 5.5) * symbolScale}
                  fill={value === undefined ? '#ffffff' : valueColor(layer!.overlay!.metric, value, loadingRange)}
                  stroke={highlighted ? '#0d7771' : historical ? '#91aaa6' : '#344c53'}
                  strokeWidth={(highlighted ? dense ? 1.8 : 2.5 : dense ? .8 : 1.5) * visualScale} />}
              {(nodes.length <= 25 || highlighted || historical || focusBuses.has(bus.id) || hovered === bus.id) &&
                <text x={bus.x + 13 * visualScale} y={bus.y - 11 * visualScale}
                  className="network-node-label"
                  style={{ fontSize: `${12 * visualScale}px`, strokeWidth: `${3 * visualScale}px` }}>{label}</text>}
              <title>{label}{'vn_kv' in bus && bus.vn_kv !== null ? ` · ${bus.vn_kv} kV` : ''}{value === undefined ? '' : ` · ${value.toFixed(3)} ${layer!.overlay!.unit}`}</title>
            </g>
          })}
        </svg>
        {geometry!.schema === 'capstone-network-diagram/1.0' && geometry!.coordinate_system === 'geographic' &&
          <span className="network-north" aria-hidden="true">N ↑</span>}
        <span className="network-canvas-hint">拖动平移 · Shift + 滚轮缩放{nodes.length > 12 ? ' · 悬停识别元件' : ''}</span>
      </div>
      <div className="network-footer">
        <div className="network-legend"><span className={schematic ? 'legend-busbar' : 'legend-bus-point'} /> 母线
          {branchKinds.has('line') && <><span className="legend-line" /> 线路</>}
          {branchKinds.has('link') && <><span className="legend-link" /> 直流连接</>}
          {[...branchKinds].some((kind) => ['transformer', 'trafo', 'trafo3w'].includes(kind)) &&
            <><span className="legend-transformer">◯◯</span> 变压器</>}
          <span className="legend-focus" /> 任务定位</div>
        {layer?.overlay ? <div className="network-overlay-note">
          <span className="overlay-gradient" /><strong>{layer!.overlay.metric === 'loading_percent' ? '线路负载率' : '母线电压'} · {layer!.overlay.unit}</strong>
          <span>{layer!.overlay.metric === 'loading_percent' && loadingRange
            ? `本轮相对色阶 ${loadingRange.min.toFixed(1)}–${loadingRange.max.toFixed(1)}% · 深红为本轮最高值，不代表越限`
            : layer!.overlay.metric === 'loading_percent' ? '暂无可比较的线路负载率' : '色阶 接近 1.0 → 偏离 1.0'}</span>
          <span>仅对 {colored} / {denominator} 条有结果的{layer!.overlay.metric === 'loading_percent' ? '线路' : '母线'}着色</span>
        </div> : view ? <span className="network-no-overlay">当前步骤暂无逐元件数值</span>
          : <span className="network-overlay-note network-no-overlay"><span className="overlay-placeholder" aria-hidden="true" />
            <strong>运行指标</strong><span>执行后显示</span></span>}
        {view?.schema === 'capstone-network-view/1.0' && (view.omitted.buses > 0 || view.omitted.branches > 0) &&
          <span className="network-omitted">预览范围：省略 {view.omitted.buses} 个母线、{view.omitted.branches} 条支路</span>}
        {hovered && <span className="network-hover-id">{hovered}{hoveredValue === undefined ? ''
          : ` · ${hoveredValue.toFixed(layer!.overlay?.metric === 'voltage_pu' ? 3 : 1)} ${layer!.overlay?.unit}`}</span>}
      </div>
  </> : <div className="network-empty" role={unavailable ? 'alert' : 'status'}><span aria-hidden="true">◇</span>
      <strong>{unavailable ? '本轮电网视图暂不可用'
        : previewUnavailable ? '案例电网暂不可用' : '正在读取案例电网…'}</strong>
      <p>{unavailable ? networkFailureCopy(failureCode)
        : previewUnavailable ? '登记模型的底图未能读取，请稍后重新打开案例。'
          : `模型：${modelName}。正在加载权威系统返回的完整拓扑。`}</p>
      {unavailable && failureCode && <small>诊断代码：{failureCode}</small>}</div>}
  </section>
}

function networkFailureCopy(code?: string): string {
  switch (code) {
    case 'diagram_limit': return '此模型的完整拓扑超过当前视图容量，无法显示。请从模型目录选择可显示的模型；已完成的回答仍可查看。'
    case 'projection_model_mismatch': return '返回的拓扑与本次指令的模型或版本不一致，已停止显示。请重试本次指令；若仍失败，可查看运行过程。'
    case 'projection_invalid': return '返回的拓扑未通过数据校验，已停止显示。请重试本次指令；若仍失败，可查看运行过程。'
    case 'projection_source_unavailable': return '电网服务未能返回本次模型的拓扑。请重试本次指令；若仍失败，可查看运行过程。'
    default: return '本次运行未取得可验证的电网拓扑。请重试本次指令或重新打开模型；已完成的回答仍可查看。'
  }
}
