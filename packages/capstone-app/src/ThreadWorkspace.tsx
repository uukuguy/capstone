import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { PageHeader } from './AppHeader'

/** Shared application frame. Controllers supply public state and capabilities. */
export default function ThreadWorkspace({ preparation, sidebar, heading, children, loading = false,
  ready = true, subtitle, headerActions, conversationOnly = false, resourcePanel, resourcePanelOpen = false, onResourcePanelOpenChange, resourceLabel = '模型与结果' }: {
  preparation?: ReactNode; sidebar?: ReactNode; heading?: ReactNode; children?: ReactNode
  loading?: boolean; ready?: boolean; subtitle?: string; headerActions?: ReactNode; conversationOnly?: boolean
  resourcePanel?: ReactNode; resourcePanelOpen?: boolean; onResourcePanelOpenChange?: (open: boolean) => void
  resourceLabel?: string
}) {
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [share, setShare] = useState(() => {
    try { const saved=Number(localStorage.getItem('capstone.workspace.conversation-share')); if (saved>=25 && saved<=70) return saved } catch { /* Use the default split. */ }
    return 45
  })
  const columns = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const [containerWidth,setContainerWidth]=useState(0)
  const minimum=containerWidth>=760 ? Math.max(25,360/containerWidth*100) : 25
  const maximum=containerWidth>=760 ? Math.min(70,(containerWidth-368)/containerWidth*100) : 70
  const effectiveShare=Math.round(Math.max(minimum,Math.min(maximum,share)))
  const resize = (value: number) => {
    const next=Math.round(Math.max(25,Math.min(70,value)))
    setShare(next)
    try { localStorage.setItem('capstone.workspace.conversation-share',String(next)) } catch { /* Keep the live ratio. */ }
  }
  useEffect(() => {
    const adapt=()=>setContainerWidth(columns.current?.getBoundingClientRect().width || 0)
    adapt()
    const observer=typeof ResizeObserver==='undefined' ? undefined : new ResizeObserver(adapt)
    if(columns.current)observer?.observe(columns.current)
    window.addEventListener('resize',adapt)
    return ()=>{observer?.disconnect();window.removeEventListener('resize',adapt)}
  },[ready,loading,resourcePanelOpen])
  const resourceToggle = useRef<HTMLButtonElement>(null)
  const closeResource = () => { setExpanded(false); onResourcePanelOpenChange?.(false); resourceToggle.current?.focus() }
  return <div className={`thread-app-shell${conversationOnly ? ' thread-conversation-workspace' : ''}${navigationOpen ? ' is-navigation-open' : ''}${resourcePanel && resourcePanelOpen ? ' has-resource-panel' : ''}${expanded ? ' is-resource-expanded' : ''}`}>
    {preparation}
    <PageHeader className="thread-page-header" showThreadEntry={false} subtitle={subtitle} actions={conversationOnly ? <>
      <button className="thread-navigation-toggle" aria-expanded={navigationOpen} aria-controls="thread-session-navigation" onClick={() => setNavigationOpen(value => !value)}>会话导航</button>
      {headerActions}
    </> : headerActions} />
    {loading && !ready ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main>
      : ready ? <main className="thread-app-main"><div ref={columns} className="thread-app-columns" style={{'--conversation-share':`${effectiveShare}%`} as CSSProperties}>
        {sidebar}
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          <div className="thread-workspace-heading">{heading}
            {resourcePanel && <button ref={resourceToggle} type="button" className="thread-control-button thread-resource-toggle" aria-expanded={resourcePanelOpen}
              aria-controls="thread-resource-panel" onClick={() => onResourcePanelOpenChange?.(!resourcePanelOpen)}>查看{resourceLabel}</button>}
          </div>
          {children}
        </section>
        {resourcePanel && resourcePanelOpen && <div className="thread-workspace-separator" role="separator" aria-label="调整对话与成果宽度" aria-orientation="vertical"
          aria-valuemin={Math.round(minimum)} aria-valuemax={Math.round(maximum)} aria-valuenow={effectiveShare} aria-valuetext={`对话 ${effectiveShare}%，成果 ${100-effectiveShare}%`} tabIndex={0}
          onKeyDown={event => {
            const delta=event.key==='ArrowLeft' ? -2 : event.key==='ArrowRight' ? 2 : 0
            if (delta || event.key==='Home' || event.key==='End') { event.preventDefault(); resize(event.key==='Home' ? 25 : event.key==='End' ? 70 : effectiveShare+delta) }
          }}
          onPointerDown={event => { if (event.button!==0) return; event.preventDefault(); event.stopPropagation(); dragging.current=true; event.currentTarget.setPointerCapture?.(event.pointerId) }}
          onPointerMove={event => { if (!dragging.current) return; event.preventDefault(); event.stopPropagation(); const bounds=columns.current?.getBoundingClientRect(); if (bounds?.width) resize((event.clientX-bounds.left)/bounds.width*100) }}
          onPointerUp={event => { dragging.current=false; event.stopPropagation(); event.currentTarget.releasePointerCapture?.(event.pointerId) }}
          onPointerCancel={()=>{dragging.current=false}} />}
        {resourcePanel && <aside id="thread-resource-panel" className="thread-resource-panel" hidden={!resourcePanelOpen} aria-label={resourceLabel}
          onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); closeResource() } }}>
          <div className="thread-resource-heading"><span>{resourceLabel}</span><div><button type="button" className="thread-control-button thread-resource-expand" onClick={()=>resize(45)}>恢复默认比例</button><button type="button" className="thread-control-button thread-resource-expand" onClick={()=>setExpanded(value=>!value)}>{expanded ? '恢复左右布局' : '扩大成果区'}</button><button type="button" className="thread-control-button" onClick={closeResource}>关闭{resourceLabel}</button></div></div>
          {resourcePanel}
        </aside>}
      </div></main> : null}
  </div>
}
