import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react'
import { AppBrand, PageHeader, WorkspaceBuildStatus } from './AppHeader'
import { Maximize2, Minimize2, RotateCcw, X, Menu, PanelRight } from 'lucide-react'
import WorkspaceProducts, { type WorkspaceProductView } from './WorkspaceProducts'
import NetworkAccessLamp from './NetworkAccessLamp'
import {readWorkspacePanels,saveWorkspacePanels} from './workspaceEntry'
import {useSessionViewState,useSessionReadingPositions} from './workspaceSessionCache'

/** Shared application frame. Controllers supply public state and capabilities. */
export default function ThreadWorkspace({ preparation, sidebar, heading, children, loading = false,
  ready = true, subtitle, headerActions, navigationFooter, conversationOnly = false, resourcePanel, resourcePanelOpen = false, onResourcePanelOpenChange, resourceLabel = '模型与结果', resourceViews, selectedResourceView, onResourceViewChange, workspaceActions, hideResourceToggle = false, resourceToggleRef,sessionKey }: {
  preparation?: ReactNode; sidebar?: ReactNode; heading?: ReactNode; children?: ReactNode; navigationFooter?: ReactNode
  loading?: boolean; ready?: boolean; subtitle?: string; headerActions?: ReactNode; conversationOnly?: boolean
  resourcePanel?: ReactNode; resourcePanelOpen?: boolean; onResourcePanelOpenChange?: (open: boolean) => void
  resourceLabel?: string
  resourceViews?: readonly WorkspaceProductView[]; selectedResourceView?: string; onResourceViewChange?: (id: string) => void
  workspaceActions?: ReactNode
  hideResourceToggle?: boolean; resourceToggleRef?: RefObject<HTMLButtonElement | null>
  sessionKey?:string
}) {
  const resourcePanelId=sessionKey?`thread-resource-panel-${sessionKey}`:'thread-resource-panel'
  const navigationPanelId=useId()
  const [navigationOpen, updateNavigationOpen] = useState(()=>{
    const saved=readWorkspacePanels(sessionKey).navigation;if(saved!==undefined)return saved
    try{const value=localStorage.getItem('capstone.workspace.navigation-open');if(value!==null)return value==='true'}catch{/* Use desktop default. */}
    return window.innerWidth>760
  })
  const setNavigationOpen=(value:boolean|((previous:boolean)=>boolean))=>updateNavigationOpen(previous=>{
    const next=typeof value==='function'?value(previous):value
    saveWorkspacePanels(sessionKey,{navigation:next})
    try{localStorage.setItem('capstone.workspace.navigation-open',String(next))}catch{/* Keep live preference. */}return next
  })
  const [navigationWidth,setNavigationWidth]=useSessionViewState('layout.navigation-width',()=>{try{const saved=Number(localStorage.getItem('capstone.workspace.navigation-width'));if(saved>=180&&saved<=360)return saved}catch{/* Default width. */}return 224})
  const navigationDragging=useRef(false),shell=useRef<HTMLDivElement>(null)
  useSessionReadingPositions(shell)
  const resizeNavigation=(value:number)=>{const next=Math.round(Math.max(180,Math.min(360,value)));setNavigationWidth(next);try{localStorage.setItem('capstone.workspace.navigation-width',String(next))}catch{/* Keep live width. */}}
  const navigationToggle=useRef<HTMLButtonElement>(null)
  const closeNavigation=()=>{setNavigationOpen(false);navigationToggle.current?.focus({preventScroll:true})}
  const [expanded, setExpanded] = useSessionViewState(sessionKey?'layout.expanded':'preparation.expanded',false)
  useEffect(()=>{if(resourcePanel)saveWorkspacePanels(sessionKey,{resource:resourcePanelOpen})},[sessionKey,resourcePanelOpen,Boolean(resourcePanel)])
  useEffect(() => { if (!resourcePanelOpen) setExpanded(false) }, [resourcePanelOpen])
  const [share, setShare] = useSessionViewState('layout.conversation-share',() => {
    try { const saved=Number(localStorage.getItem('capstone.workspace.conversation-share')); if (saved>=25 && saved<=70) return saved } catch { /* Use the default split. */ }
    return 60
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
  const closeResource = () => { setExpanded(false); onResourcePanelOpenChange?.(false); (resourceToggleRef?.current || resourceToggle.current)?.focus() }
  const headingBar=<div className={conversationOnly ? 'workspace-workhead' : 'thread-workspace-heading'}>{heading}
    <div className="workspace-session-tools" role="group" aria-label="会话工具">
    {!expanded && workspaceActions}
    {resourcePanel && !hideResourceToggle && <button ref={resourceToggle} type="button" className="thread-control-button thread-resource-toggle" aria-expanded={resourcePanelOpen}
      aria-label={conversationOnly ? (resourcePanelOpen ? '收起展示区' : '打开展示区') : `查看${resourceLabel}`} title={conversationOnly ? (resourcePanelOpen ? '收起展示区' : '打开展示区') : resourceLabel} aria-controls={resourcePanelId} onClick={() => { setExpanded(false); onResourcePanelOpenChange?.(!resourcePanelOpen) }}><PanelRight size={16} aria-hidden="true"/>{!conversationOnly && <span>{resourceLabel==='成果'?'任务成果':resourceLabel}</span>}</button>}
    </div>
  </div>
  const conversation=<section className="thread-chat-pane" aria-label="Thread 对话区">{!conversationOnly && headingBar}{children}</section>
  const body=loading && !ready ? <div className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</div>
    : ready ? <div ref={columns} className="thread-app-columns" style={{'--conversation-share':`${effectiveShare}%`} as CSSProperties}>
      {!conversationOnly && sidebar}
      {conversation}
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
      {resourcePanel && <aside id={resourcePanelId} className="thread-resource-panel" hidden={!resourcePanelOpen} aria-label={resourceLabel}
        onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); closeResource() } }}>
        <WorkspaceProducts views={resourceViews || [{id:'resource',label:resourceLabel,content:resourcePanel}]} selectedId={selectedResourceView} onSelect={onResourceViewChange}
          actions={<>
            <button type="button" className="workspace-product-icon thread-resource-expand" aria-label="恢复默认比例" title="恢复默认比例" onClick={()=>resize(60)}><RotateCcw aria-hidden="true" /></button>
            <button type="button" className="workspace-product-icon thread-resource-expand" aria-label={expanded ? '恢复左右布局' : '扩大成果区'} title={expanded ? '恢复左右布局' : '扩大成果区'} onClick={()=>setExpanded(value=>!value)}>{expanded ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}</button>
            <button type="button" className="workspace-product-icon" aria-label={`关闭${resourceLabel}`} title={`关闭${resourceLabel}`} onClick={closeResource}><X aria-hidden="true" /></button>
          </>} />
      </aside>}
    </div> : null
  return <div ref={shell} style={{'--navigation-width':`${navigationWidth}px`}as CSSProperties} className={`thread-app-shell${conversationOnly ? ' thread-conversation-workspace' : ''}${navigationOpen ? ' is-navigation-open' : ''}${resourcePanel && resourcePanelOpen ? ' has-resource-panel' : ''}${expanded ? ' is-resource-expanded' : ''}`}>
    {preparation}
    {conversationOnly ? <>
      {navigationOpen && <button className="workspace-navigation-backdrop" aria-label="关闭会话导航遮罩" tabIndex={-1} onClick={closeNavigation} />}
      <aside id={navigationPanelId} className="workspace-navigation" hidden={!navigationOpen} aria-label="工作空间导航">
        {navigationOpen && <button type="button" className="workspace-navigation-close" aria-label="收起会话导航" onClick={closeNavigation}><X size={18} aria-hidden="true" /></button>}
        <div className="workspace-brand"><div><AppBrand /><NetworkAccessLamp /></div><span>WORKSPACE</span></div>
        {sidebar}
        <footer className="workspace-navfoot">{navigationFooter}<span>企业工作空间</span><WorkspaceBuildStatus /></footer>
      </aside>
      {navigationOpen&&sidebar&&<div className="workspace-navigation-separator" role="separator" aria-label="调整会话栏宽度" aria-orientation="vertical" tabIndex={0}
        aria-valuemin={180} aria-valuemax={360} aria-valuenow={navigationWidth}
        onDoubleClick={()=>resizeNavigation(224)}
        onKeyDown={event=>{const delta=event.key==='ArrowLeft'?-8:event.key==='ArrowRight'?8:0;if(delta||event.key==='Home'||event.key==='End'){event.preventDefault();resizeNavigation(event.key==='Home'?180:event.key==='End'?360:navigationWidth+delta)}}}
        onPointerDown={event=>{if(event.button!==0)return;event.preventDefault();navigationDragging.current=true;event.currentTarget.setPointerCapture?.(event.pointerId)}}
        onPointerMove={event=>{if(navigationDragging.current)resizeNavigation(event.clientX-(shell.current?.getBoundingClientRect().left??0))}}
        onPointerUp={event=>{navigationDragging.current=false;event.currentTarget.releasePointerCapture?.(event.pointerId)}} onPointerCancel={()=>{navigationDragging.current=false}}/>}
      <main className="workspace-shell">
        <header className="workspace-topbar" aria-label="工作空间">
          <button ref={navigationToggle} type="button" className="thread-navigation-toggle" aria-label="会话导航" aria-expanded={navigationOpen} aria-controls={navigationPanelId} onClick={()=>setNavigationOpen(value=>!value)}><Menu aria-hidden="true" /></button>
          {headingBar}
          <div className="workspace-top-actions">{headerActions}</div>
        </header>
        {body}
      </main>
    </> : <><PageHeader className="thread-page-header" showThreadEntry={false} subtitle={subtitle} actions={headerActions} /><main className="thread-app-main">{body}</main></>}
  </div>
}
