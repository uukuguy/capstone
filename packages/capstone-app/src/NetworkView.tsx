import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent, WheelEvent } from 'react'
import { layoutNetwork } from './networkLayout'
import type { PositionedBus } from './networkLayout'
import type { NetworkView as NetworkViewData } from './types'

type Camera = { x: number; y: number; width: number; height: number }
const FULL: Camera = { x: 0, y: 0, width: 1000, height: 600 }

function taskCamera(view: NetworkViewData, buses: PositionedBus[], focusIds: string[]): Camera {
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
  const nodes = useMemo(() => view ? layoutNetwork(view) : [], [view])
  const byId = useMemo(() => new Map(nodes.map((bus) => [bus.id, bus])), [nodes])
  const values = useMemo(() => new Map(view?.overlay?.values.map((item) => [item.id, item.value]) || []), [view])
  const focusIds = useMemo(() => view ? nextTask ? view.next_focus_ids : view.focus_ids : [], [view, nextTask])

  useEffect(() => {
    setCamera(view ? taskCamera(view, nodes, focusIds) : FULL)
  }, [focusKey, view, nodes, focusIds])

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

  const colored = view?.overlay?.values.length || 0
  const hoveredValue = hovered === null ? undefined : values.get(hovered)
  const denominator = view?.overlay?.metric === 'voltage_pu'
    ? view.buses.length : view?.branches.filter((branch) => branch.kind === 'line').length || 0
  return <section className="network-card" aria-labelledby="network-title">
    <div className="network-head"><div><span className="eyebrow">MODEL / CURRENT RUN</span>
      <h2 id="network-title">电网视图</h2></div><span className="network-model">{modelName}</span></div>
    {view ? <>
      <div className="network-meta"><span>模型结构 · {view.model.source}</span>
        <span>{view.coordinate_status === 'schematic-required' ? '示意布局' : '模型坐标 · 未经地理校验'}</span></div>
      <div className="network-toolbar" aria-label="电网图操作">
        <button type="button" onClick={() => zoom(0.8)} aria-label="放大">＋</button>
        <button type="button" onClick={() => zoom(1.25)} aria-label="缩小">－</button>
        <span className="network-toolbar-divider" />
        <button type="button" onClick={() => setCamera(FULL)}>适配全图</button>
        <button type="button" onClick={() => setCamera(taskCamera(view, nodes, focusIds))}>回到当前任务</button>
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
          {view.branches.map((branch) => {
            const from = byId.get(branch.from_bus), to = byId.get(branch.to_bus)
            if (!from || !to) return null
            const value = values.get(branch.id)
            const highlighted = focusIds.includes(branch.id)
            const color = value === undefined ? highlighted ? '#187b78' :
              branch.kind === 'link' ? '#718ca0' : '#aab9b9'
              : valueColor(view.overlay!.metric, value)
            return <g key={branch.id} onMouseEnter={() => setHovered(branch.id)}
              onMouseLeave={() => setHovered(null)}>
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke="transparent" strokeWidth="20" />
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={color} strokeWidth={highlighted ? 7 : value === undefined ? 3 : 5}
                strokeDasharray={branch.kind === 'link' ? '9 6' : undefined}
                strokeLinecap="round" />
              <title>{branch.label}{value === undefined ? '' : ` · ${value.toFixed(1)} ${view.overlay!.unit}`}</title>
            </g>
          })}
          {nodes.map((bus) => {
            const value = values.get(bus.id)
            const highlighted = focusIds.includes(bus.id)
            return <g key={bus.id} onMouseEnter={() => setHovered(bus.id)}
              onMouseLeave={() => setHovered(null)}>
              <circle cx={bus.x} cy={bus.y} r={highlighted ? 11 : 8}
                fill={value === undefined ? '#ffffff' : valueColor(view.overlay!.metric, value)}
                stroke={highlighted ? '#0d7771' : '#344c53'} strokeWidth={highlighted ? 3 : 2} />
              <text x={bus.x + 13} y={bus.y - 11} className="network-node-label">{bus.label}</text>
              <title>{bus.label}{value === undefined ? '' : ` · ${value.toFixed(3)} ${view.overlay!.unit}`}</title>
            </g>
          })}
        </svg>
        <span className="network-canvas-hint">拖动平移 · 滚轮缩放</span>
      </div>
      <div className="network-footer">
        <div className="network-legend"><span className="legend-line" /> 线路 <span className="legend-link" /> Link
          <span className="legend-focus" /> 当前任务</div>
        {view.overlay ? <div className="network-overlay-note">
          <span className="overlay-gradient" /><strong>{view.overlay.metric === 'loading_percent' ? '线路负载率' : '母线电压'} · {view.overlay.unit}</strong>
          <span>{view.overlay.metric === 'loading_percent' ? '色阶 0–120%' : '色阶 接近 1.0 → 偏离 1.0'}</span>
          <span>仅对 {colored} / {denominator} 条有结果的{view.overlay.metric === 'loading_percent' ? '线路' : '母线'}着色</span>
        </div> : <span className="network-no-overlay">当前步骤暂无逐元件数值</span>}
        {(view.omitted.buses > 0 || view.omitted.branches > 0) &&
          <span className="network-omitted">预览范围：省略 {view.omitted.buses} 个母线、{view.omitted.branches} 条支路</span>}
        {hovered && <span className="network-hover-id">{hovered}{hoveredValue === undefined ? ''
          : ` · ${hoveredValue.toFixed(view.overlay?.metric === 'voltage_pu' ? 3 : 1)} ${view.overlay?.unit}`}</span>}
      </div>
  </> : <div className="network-empty"><span aria-hidden="true">◇</span>
      <strong>{unavailable ? '本轮电网视图暂不可用' : '运行首步后显示登记模型拓扑'}</strong>
      <p>{unavailable ? '当前运行没有可验证的模型投影；已提交回答仍可查看。'
        : `模型：${modelName}。图中仅显示权威系统返回的受限结构。`}</p></div>}
  </section>
}
