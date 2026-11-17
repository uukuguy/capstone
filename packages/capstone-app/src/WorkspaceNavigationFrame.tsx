import {useCallback,useEffect,useId,useMemo,useRef,useState,type CSSProperties,type ReactNode} from 'react'
import {X} from 'lucide-react'
import {AppBrand,WorkspaceBuildStatus} from './AppHeader'
import NetworkAccessLamp from './NetworkAccessLamp'
import ControlGoalPanel from './ControlGoalPanel'
import SessionNavigation,{navigateSession} from './SessionNavigation'
import SessionNewPopover from './SessionNewPopover'
import {HttpThreadTransport} from './threadHttpTransport'
import {readThreadAccess} from './threadAccess'
import {currentWorkspaceName} from './workspaceName'
import {useSessionCatalog,mergeSessionPage} from './sessionCatalog'
import {sessionManagement} from './sessionManagement'
import {WorkspaceNavigationContext} from './workspaceNavigationContext'
import './workspaceNavigation.css'
import {WorkspaceGatewayStatus} from './WorkspaceConnectionStatus'
import type {GatewayConnectionStatus} from './threadInput'

/** The navigation lifetime is the workspace lifetime, never a retained Thread. */
export default function WorkspaceNavigationFrame({namespace,currentId,children}:{namespace:string;currentId:string;children:ReactNode}){
  const panelId=useId(),toggleRef=useRef<HTMLButtonElement>(null)
  const [open,setOpen]=useState(()=>{
    try{const saved=localStorage.getItem('capstone.workspace.navigation-open');if(saved!==null)return saved==='true'}catch{/* Use desktop default. */}
    return window.innerWidth>760
  })
  const [width,setWidth]=useState(()=>{
    try{const n=Number(localStorage.getItem('capstone.workspace.navigation-width'));if(n>=180&&n<=360)return n}catch{/* Use default width. */}
    return 224
  })
  const [gateway,setGateway]=useState<{threadId:string;value:GatewayConnectionStatus|undefined}>()
  const connectionChanged=useCallback((value:GatewayConnectionStatus|undefined)=>setGateway({threadId:currentId,value}),[currentId])
  const dragging=useRef(false),shell=useRef<HTMLDivElement>(null)
  const [transport,setTransport]=useState<HttpThreadTransport>()
  const [sessions,setSessions]=useSessionCatalog(namespace)
  const [revision,setRevision]=useState(0),[error,setError]=useState(false)
  const refreshCatalog=useCallback(()=>setRevision(value=>value+1),[])
  const origin=import.meta.env.VITE_API_ORIGIN||'',workspace=currentWorkspaceName()
  useEffect(()=>{
    const controller=new AbortController()
    void readThreadAccess(origin,controller.signal).then(access=>{
      if(controller.signal.aborted)return
      const token=access==='open'?'':sessionStorage.getItem('capstone.thread.operatorToken')||''
      if(access==='operator'&&!token)return
      setTransport(new HttpThreadTransport(origin,token,fetch,'/api/v1/threads','2',workspace))
    }).catch(()=>{if(!controller.signal.aborted)setError(true)})
    return()=>controller.abort()
  },[origin,namespace,workspace])
  useEffect(()=>{
    const refresh=()=>setRevision(value=>value+1)
    const reveal=()=>{if(document.visibilityState==='visible')refresh()}
    window.addEventListener('capstone-session-renamed',refresh)
    window.addEventListener('capstone-session-created',refresh)
    window.addEventListener('focus',refresh)
    document.addEventListener('visibilitychange',reveal)
    return()=>{window.removeEventListener('capstone-session-renamed',refresh);window.removeEventListener('capstone-session-created',refresh);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',reveal)}
  },[])
  useEffect(()=>{
    if(!transport)return
    const controller=new AbortController()
    void transport.listThreads(false,undefined,controller.signal).then(page=>{
      if(!controller.signal.aborted){setSessions(previous=>mergeSessionPage(previous,page));setError(false)}
    }).catch(()=>{if(!controller.signal.aborted)setError(true)})
    return()=>controller.abort()
    // Selection is deliberately not a catalog invalidation.
  },[transport,revision])
  const actions=useMemo(()=>transport?sessionManagement(transport,()=>setRevision(value=>value+1)):undefined,[transport])
  const changeOpen=(value:boolean)=>{setOpen(value);try{localStorage.setItem('capstone.workspace.navigation-open',String(value))}catch{/* Keep live state. */}}
  const resize=(value:number)=>{const next=Math.round(Math.max(180,Math.min(360,value)));setWidth(next);try{localStorage.setItem('capstone.workspace.navigation-width',String(next))}catch{/* Keep live width. */}}
  const close=()=>{changeOpen(false);toggleRef.current?.focus({preventScroll:true})}
  const context=useMemo(()=>({open,panelId,toggleRef,gateway:gateway?.threadId===currentId?gateway.value:undefined,catalog:sessions,refreshCatalog,toggle:()=>changeOpen(!open)}),[open,panelId,gateway,currentId,sessions,refreshCatalog])
  return <WorkspaceNavigationContext.Provider value={context}>
    <div ref={shell} className={`thread-app-shell thread-conversation-workspace workspace-route-frame${open?' is-navigation-open':''}`} style={{'--navigation-width':`${width}px`} as CSSProperties}>
      {open&&<button className="workspace-navigation-backdrop" aria-label="关闭会话导航遮罩" tabIndex={-1} onClick={close}/>}
      <aside id={panelId} className="workspace-navigation" hidden={!open} aria-label="工作空间导航">
        {open&&<button type="button" className="workspace-navigation-close" aria-label="收起会话导航" onClick={close}><X size={18} aria-hidden="true"/></button>}
        <div className="workspace-brand"><div><AppBrand/><NetworkAccessLamp/></div><span className="workspace-identity"><small>WORKSPACE</small><strong title={workspace}>{workspace}</strong></span></div>
        <nav className="thread-session-navigation" aria-label="任务会话">
          {transport&&<ControlGoalPanel transport={transport} onOpenThread={(threadId,workId)=>{
            try{const key=`${namespace}.${threadId}.work-draft`,saved=JSON.parse(sessionStorage.getItem(key)||'{}');sessionStorage.setItem(key,JSON.stringify({...saved,selected:workId}))}catch{/* Keep existing drafts. */}
            window.dispatchEvent(new CustomEvent('capstone-work-selected',{detail:{threadId,workId}}))
            navigateSession(threadId)
          }}/>}
          <SessionNewPopover onCreated={navigateSession}/>
          {error&&<p className="workspace-catalog-status" role="status">会话列表暂不可用，当前会话仍可使用。</p>}
          <SessionNavigation items={sessions?.threads??[]} currentId={currentId} storageKey={namespace} actions={actions}/>
        </nav>
        <footer className="workspace-navfoot"><div className="workspace-navigation-gateway">{transport&&<WorkspaceGatewayStatus transport={transport} threadId={currentId==='new'?undefined:currentId} onConnection={connectionChanged}/>}</div><WorkspaceBuildStatus/></footer>
      </aside>
      {open&&<div className="workspace-navigation-separator" role="separator" aria-label="调整会话栏宽度" aria-orientation="vertical" tabIndex={0} aria-valuemin={180} aria-valuemax={360} aria-valuenow={width}
        onDoubleClick={()=>resize(224)} onKeyDown={event=>{const delta=event.key==='ArrowLeft'?-8:event.key==='ArrowRight'?8:0;if(delta||event.key==='Home'||event.key==='End'){event.preventDefault();resize(event.key==='Home'?180:event.key==='End'?360:width+delta)}}}
        onPointerDown={event=>{if(event.button!==0)return;event.preventDefault();dragging.current=true;event.currentTarget.setPointerCapture?.(event.pointerId)}}
        onPointerMove={event=>{if(dragging.current)resize(event.clientX-(shell.current?.getBoundingClientRect().left??0))}}
        onPointerUp={event=>{dragging.current=false;event.currentTarget.releasePointerCapture?.(event.pointerId)}} onPointerCancel={()=>{dragging.current=false}}/>}
      <div className="workspace-route-content">{children}</div>
    </div>
  </WorkspaceNavigationContext.Provider>
}
