import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent, WheelEvent } from 'react'
import { layoutNetwork, usesModelCoordinates } from './networkLayout'
import type { PositionedBus } from './networkLayout'
import type { LegacyNetworkView, NetworkDiagram, NetworkView as NetworkViewData } from './types'

type Camera = { x: number; y: number; width: number; height: number }
const FULL: Camera = { x: 0, y: 0, width: 1000, height: 600 }

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

function valueColor(metric: 'loading_percent' | 'voltage_pu', value: number): string {
  if (metric === 'voltage_pu') {
    const deviation = Math.min(1, Math.abs(value - 1) / 0.15)
    return `hsl(${Math.round(178 - deviation * 160)} 65% 39%)`
  }
  return `hsl(${Math.round(178 - Math.min(1, Math.max(0, value) / 120) * 166)} 68% 40%)`
}

export function NetworkView({ view, modelName, focusKey, nextTask = false, unavailable = false }: {
  view: NetworkViewData | null; modelName: string; focusKey: string
  nextTask?: boolean; unavailable?: boolean
}) {
  const [camera, setCamera] = useState<Camera>(FULL)
  const [hovered, setHovered] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; camera: Camera } | null>(null)
  const geometry = view?.schema === 'capstone-network-view/2.0' ? view.diagram : view
  const layer = view?.schema === 'capstone-network-view/2.0' ? view.layer : view
  const viewIdentity = view?.schema === 'capstone-network-view/2.0'
    ? `${view.diagram.ref}:${view.ordinal}:${view.layer.focus_ids.join(',')}:${view.layer.next_focus_ids.join(',')}`
    : view ? `${view.model.revision}:${view.ordinal}:${view.focus_ids.join(',')}:${view.next_focus_ids.join(',')}` : 'empty'
  const nodes = useMemo(() => geometry ? layoutNetwork(geometry) : [], [geometry])
  const modelCoordinates = useMemo(() => geometry ? usesModelCoordinates(geometry) : false, [geometry])
  const byId = useMemo(() => new Map(nodes.map((bus) => [bus.id, bus])), [nodes])
  const values = useMemo(() => new Map(layer?.overlay?.values.map((item) => [item.id, item.value]) || []), [layer])
  const focusIds = useMemo(() => layer ? nextTask ? layer.next_focus_ids : layer.focus_ids : [], [layer, nextTask])
  const focusBuses = useMemo(() => new Set(geometry?.branches.filter((branch) =>
    focusIds.includes(branch.id)).flatMap((branch) => [branch.from_bus, branch.to_bus]) || []), [geometry, focusIds])

  useEffect(() => {
    setCamera(geometry ? taskCamera(geometry, nodes, focusIds) : FULL)
    // Focus changes on step/execution transitions or on arrival of a different diagram.
  }, [focusKey, viewIdentity])

  function zoom(factor: number, clientX?: number, clientY?: number, target?: SVGSVGElement) {
    setCamera((before) => {
      const width = Math.max(220, Math.min(1500, before.width * factor))
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
  const branchKinds = new Set(geometry?.branches.map((branch) => branch.kind) || [])
  return <section className="network-card" aria-labelledby="network-title">
    <div className="network-head"><div><span className="eyebrow">MODEL / CURRENT RUN</span>
      <h2 id="network-title">电网视图</h2></div><span className="network-model">{modelName}</span></div>
    {view ? <>
      <div className="network-meta"><span>模型结构 · {geometry!.model.source} · {geometry!.buses.length} 母线 / {geometry!.branches.length} 支路</span>
        <span>{geometry!.schema === 'capstone-network-diagram/1.0'
          ? geometry!.coordinate_system === 'geographic' ? '地理拓扑 · 模型坐标' : modelCoordinates ? '电气示意 · 模型坐标' : '电气示意布局'
          : modelCoordinates ? '模型坐标 · 未经地理校验'
            : geometry!.coordinate_status === 'provided-unverified' ? '示意布局 · 模型坐标过密' : '示意布局'}</span></div>
      <div className="network-toolbar" aria-label="电网图操作">
        <button type="button" onClick={() => zoom(0.8)} aria-label="放大">＋</button>
        <button type="button" onClick={() => zoom(1.25)} aria-label="缩小">－</button>
        <span className="network-toolbar-divider" />
        <button type="button" onClick={() => setCamera(FULL)}>适配全图</button>
        <button type="button" onClick={() => setCamera(taskCamera(geometry!, nodes, focusIds))}>回到当前任务</button>
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
            const value = values.get(branch.id)
            const highlighted = focusIds.includes(branch.id)
            const color = value === undefined ? highlighted ? '#187b78' :
              branch.kind === 'link' ? '#718ca0' : '#829c98'
              : valueColor(layer!.overlay!.metric, value)
            const transformer = ['transformer', 'trafo', 'trafo3w'].includes(branch.kind)
            const centerX = (from.x + to.x) / 2, centerY = (from.y + to.y) / 2
            return <g key={branch.id} onMouseEnter={() => setHovered(branch.id)}
              onMouseLeave={() => setHovered(null)}>
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke="transparent" strokeWidth={dense ? 7 : 20} />
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={color} strokeWidth={highlighted ? dense ? 3 : 6 : dense ? 1.5 : value === undefined ? 2.5 : 4}
                strokeDasharray={branch.kind === 'link' ? '9 6' : undefined}
                strokeLinecap="round" />
              {transformer && <g className="network-transformer-symbol" aria-hidden="true">
                <circle cx={centerX - (dense ? 2.3 : 4)} cy={centerY} r={dense ? 2.7 : 4.5} />
                <circle cx={centerX + (dense ? 2.3 : 4)} cy={centerY} r={dense ? 2.7 : 4.5} />
              </g>}
              {highlighted && <text x={centerX + 7} y={centerY - 9}
                className="network-branch-label">{branch.label}</text>}
              <title>{branch.label}{value === undefined ? '' : ` · ${value.toFixed(1)} ${layer!.overlay!.unit}`}</title>
            </g>
          })}
          {nodes.map((bus) => {
            const value = values.get(bus.id)
            const highlighted = focusIds.includes(bus.id)
            return <g key={bus.id} onMouseEnter={() => setHovered(bus.id)}
              onMouseLeave={() => setHovered(null)}>
              <circle cx={bus.x} cy={bus.y} r={highlighted ? dense ? 5 : 9 : dense ? 2.9 : 5.5}
                fill={value === undefined ? '#ffffff' : valueColor(layer!.overlay!.metric, value)}
                stroke={highlighted ? '#0d7771' : '#344c53'} strokeWidth={highlighted ? dense ? 1.8 : 2.5 : dense ? .8 : 1.5} />
              {(nodes.length <= 25 || highlighted || focusBuses.has(bus.id) || hovered === bus.id) &&
                <text x={bus.x + 13} y={bus.y - 11} className="network-node-label">{bus.label}</text>}
              <title>{bus.label}{'vn_kv' in bus && bus.vn_kv !== null ? ` · ${bus.vn_kv} kV` : ''}{value === undefined ? '' : ` · ${value.toFixed(3)} ${layer!.overlay!.unit}`}</title>
            </g>
          })}
        </svg>
        {geometry!.schema === 'capstone-network-diagram/1.0' && geometry!.coordinate_system === 'geographic' &&
          <span className="network-north" aria-hidden="true">N ↑</span>}
        <span className="network-canvas-hint">拖动平移 · 滚轮缩放{nodes.length > 12 ? ' · 悬停识别元件' : ''}</span>
      </div>
      <div className="network-footer">
        <div className="network-legend"><span className="legend-bus" /> 母线
          {branchKinds.has('line') && <><span className="legend-line" /> 线路</>}
          {branchKinds.has('link') && <><span className="legend-link" /> 直流连接</>}
          {[...branchKinds].some((kind) => ['transformer', 'trafo', 'trafo3w'].includes(kind)) &&
            <><span className="legend-transformer">◯◯</span> 变压器</>}
          <span className="legend-focus" /> 任务定位</div>
        {layer!.overlay ? <div className="network-overlay-note">
          <span className="overlay-gradient" /><strong>{layer!.overlay.metric === 'loading_percent' ? '线路负载率' : '母线电压'} · {layer!.overlay.unit}</strong>
          <span>{layer!.overlay.metric === 'loading_percent' ? '色阶 0–120%' : '色阶 接近 1.0 → 偏离 1.0'}</span>
          <span>仅对 {colored} / {denominator} 条有结果的{layer!.overlay.metric === 'loading_percent' ? '线路' : '母线'}着色</span>
        </div> : <span className="network-no-overlay">当前步骤暂无逐元件数值</span>}
        {view.schema === 'capstone-network-view/1.0' && (view.omitted.buses > 0 || view.omitted.branches > 0) &&
          <span className="network-omitted">预览范围：省略 {view.omitted.buses} 个母线、{view.omitted.branches} 条支路</span>}
        {hovered && <span className="network-hover-id">{hovered}{hoveredValue === undefined ? ''
          : ` · ${hoveredValue.toFixed(layer!.overlay?.metric === 'voltage_pu' ? 3 : 1)} ${layer!.overlay?.unit}`}</span>}
      </div>
  </> : <div className="network-empty"><span aria-hidden="true">◇</span>
      <strong>{unavailable ? '本轮电网视图暂不可用' : '运行首步后显示登记模型拓扑'}</strong>
      <p>{unavailable ? '当前运行没有可验证的模型投影；已提交回答仍可查看。'
        : `模型：${modelName}。图中仅显示权威系统返回的受限结构。`}</p></div>}
  </section>
}
