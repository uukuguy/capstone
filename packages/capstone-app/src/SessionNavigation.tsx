import {useEffect,useLayoutEffect,useRef,useState} from 'react'
import {createPortal} from 'react-dom'
import {Archive,ChevronLeft,ChevronRight,History,Pin,Pencil,Trash2} from 'lucide-react'
import SessionRow from './SessionRow'
import SessionCleanup from './SessionCleanup'
import {navigateSession,sessionName,orderSessions,useSessionPins,type SessionNavItem} from './sessionNavigationState'
import type {SessionManagementActions} from './sessionManagement'
import type {ThreadListPage} from './threadManagement'
import {currentWorkspaceName,isWorkspaceActive} from './workspaceName'
export {navigateSession,sessionName,type SessionNavItem} from './sessionNavigationState'

export function SessionAdjacentControls({items,currentId,storageKey}: {items:readonly SessionNavItem[];currentId?:string;storageKey?:string}) {
  const {pins}=useSessionPins(storageKey),ordered=orderSessions(items,pins)
  const index=ordered.findIndex(item=>item.threadId===currentId),previous=index>0?ordered[index-1]:undefined,next=index>=0?ordered[index+1]:undefined
  return <span className="session-adjacent-controls" role="group" aria-label="切换会话">
    <button type="button" className="thread-control-button" aria-label="上一会话" title={previous?`上一会话：${sessionName(previous)}`:'已是首个会话'} disabled={!previous} onClick={()=>previous&&navigateSession(previous.threadId)}><ChevronLeft size={16} aria-hidden="true" /></button>
    <button type="button" className="thread-control-button" aria-label="下一会话" title={next?`下一会话：${sessionName(next)}`:'已是最后一个会话'} disabled={!next} onClick={()=>next&&navigateSession(next.threadId)}><ChevronRight size={16} aria-hidden="true" /></button>
  </span>
}

/** List preferences stay local. Mutations use the supplied host management ports. */
export default function SessionNavigation({items,currentId,storageKey='workspace',actions}: {items:readonly SessionNavItem[];currentId?:string;storageKey?:string;actions?:SessionManagementActions}) {
  const list=useRef<HTMLDivElement>(null),menuElement=useRef<HTMLDivElement>(null)
  const {pins,toggle}=useSessionPins(storageKey)
  const [menu,setMenu]=useState<{item:SessionNavItem;x:number;y:number}>(),[editing,setEditing]=useState<string>()
  const [archiveView,setArchiveView]=useState(false),[archived,setArchived]=useState<ThreadListPage>(),[loading,setLoading]=useState(false)
  const archiveRequest=useRef(0)
  const workspace=useRef(currentWorkspaceName()),mounted=useRef(true)
  const mayUpdate=()=>mounted.current&&isWorkspaceActive(workspace.current)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;archiveRequest.current++}},[])
  const [removed,setRemoved]=useState<string[]>([]),[names,setNames]=useState<Record<string,string>>({}),[deleting,setDeleting]=useState<SessionNavItem>(),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [reopened,setReopened]=useState<SessionNavItem[]>([])
  useEffect(()=>{if(reopened.some(item=>items.some(existing=>existing.threadId===item.threadId)))setReopened(previous=>previous.filter(item=>!items.some(existing=>existing.threadId===item.threadId)))},[items,reopened])
  const recent=[...reopened.filter(item=>!items.some(existing=>existing.threadId===item.threadId)),...items]
  const displayed=(archiveView?archived?.threads??[]:orderSessions(recent,pins)).filter(item=>!removed.includes(item.threadId)).map(item=>names[item.threadId]?{...item,sessionTitle:{text:names[item.threadId],source:'user' as const,revision:item.sessionTitle?.revision??0,source_ref:null}}:item)
  const scrollKey=`capstone.session-navigation.scroll:${storageKey}:${archiveView?'archived':'active'}`
  useLayoutEffect(()=>{
    const container=list.current;if(!container)return
    // A short/loading or hidden list cannot yet contain its saved position.
    // Retain that target until content arrives, unless the user starts scrolling.
    let pending:number|undefined,position=0,userScrolling=false
    try{const value=Number(sessionStorage.getItem(scrollKey));pending=Number.isFinite(value)&&value>=0?value:0}catch{/* Keep scroll. */}
    position=pending??0
    const visible=()=>container.clientHeight>0&&!container.closest('[hidden]')
    const restore=()=>{
      if(pending===undefined)return
      // scrollTop is fractional; scrollHeight/clientHeight round to integers.
      if(!visible())return
      const maximum=Math.max(0,container.scrollHeight-container.clientHeight)
      if(maximum+1<pending){container.scrollTop=maximum;return}
      container.scrollTop=pending
      if(Math.abs(container.scrollTop-pending)<2)pending=undefined
    }
    const save=()=>{
      if(pending!==undefined||!visible())return
      // Mount/layout/focus scroll events must not replace the shared position.
      // Only an explicit scroll gesture grants this visible list write access.
      if(!userScrolling){pending=position;restore();return}
      position=container.scrollTop
      try{sessionStorage.setItem(scrollKey,String(container.scrollTop))}catch{/* Keep scroll. */}
    }
    const cancel=()=>{pending=undefined;userScrolling=true;position=container.scrollTop}
    const key=(event:KeyboardEvent)=>{if(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' ','Tab'].includes(event.key)&&!(event.target instanceof Element&&event.target.closest('input,textarea,[contenteditable=true]')))cancel()}
    const pointer=(event:PointerEvent)=>{if(event.target===container)cancel()}
    // End/PageDown and scrollbar dragging can change scrollTop before the next
    // animation-frame scroll event. Capture it before routing hides this DOM.
    const checkpoint=()=>{if(userScrolling)save();userScrolling=false}
    container.addEventListener('scroll',save,{passive:true})
    container.addEventListener('wheel',cancel,{passive:true});container.addEventListener('touchstart',cancel,{passive:true});container.addEventListener('keydown',key);container.addEventListener('pointerdown',pointer)
    window.addEventListener('popstate',checkpoint,true);window.addEventListener('pagehide',checkpoint)
    const observer=new MutationObserver(restore);observer.observe(container,{childList:true,subtree:true})
    const resize=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(restore)
    resize?.observe(container);if(container.firstElementChild)resize?.observe(container.firstElementChild)
    restore()
    return()=>{
      // Scroll events already persist visible positions. Hidden Activity teardown
      // must not overwrite another retained session's newer global position.
      observer.disconnect();resize?.disconnect();container.removeEventListener('scroll',save)
      container.removeEventListener('wheel',cancel);container.removeEventListener('touchstart',cancel);container.removeEventListener('keydown',key);container.removeEventListener('pointerdown',pointer)
      window.removeEventListener('popstate',checkpoint,true);window.removeEventListener('pagehide',checkpoint)
    }
  },[scrollKey])
  useEffect(()=>{
    if(!menu)return
    menuElement.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const close=(event:PointerEvent)=>{if(!menuElement.current?.contains(event.target as Node))setMenu(undefined)}
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape')setMenu(undefined);else if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();const buttons=[...(menuElement.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')??[])],i=buttons.indexOf(document.activeElement as HTMLButtonElement);buttons[(i+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus()}}
    document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key)}
  },[menu])
  async function loadArchive(before?:string){
    if(!actions)return
    const request=++archiveRequest.current
    setLoading(true);setError('')
    try{
      const page=await actions.archived(before)
      if(request!==archiveRequest.current||!mayUpdate())return
      setArchived(previous=>before?{...page,threads:[...(previous?.threads??[]),...page.threads]}:page)
    }catch{if(request===archiveRequest.current)setError('归档会话暂时无法读取')}
    finally{if(request===archiveRequest.current)setLoading(false)}
  }
  async function openSession(item:SessionNavItem){
    if(!archiveView){navigateSession(item.threadId);return}
    if(!actions||busy)return
    const request=++archiveRequest.current
    setBusy(true);setLoading(false);setError('')
    try{
      await actions.archive(item.threadId,false)
      if(request!==archiveRequest.current||!mayUpdate())return
      setReopened(previous=>[{...item,archived:false},...previous.filter(value=>value.threadId!==item.threadId)])
      setRemoved(previous=>previous.filter(id=>id!==item.threadId));setArchiveView(false);setMenu(undefined)
      navigateSession(item.threadId)
    }catch{if(request===archiveRequest.current)setError('会话恢复失败，请重试。')}
    finally{setBusy(false)}
  }
  async function archive(item:SessionNavItem,value:boolean){if(!actions||busy)return;setBusy(true);setMenu(undefined);setError('');try{await actions.archive(item.threadId,value);if(!mayUpdate())return;setRemoved(previous=>[...previous,item.threadId]);if(item.threadId===currentId&&value)navigateSession(displayed.find(other=>other.threadId!==item.threadId)?.threadId??'new')}catch{setError('操作未完成；运行中的会话需先停止。')}finally{setBusy(false)}}
  const rows=(values:SessionNavItem[])=>values.map(item=><SessionRow key={item.threadId} item={item} current={item.threadId===currentId} editing={editing===item.threadId} onEdit={()=>setEditing(previous=>previous===item.threadId?undefined:item.threadId)}
    onActivate={()=>void openSession(item)}
    onRename={actions?async text=>{await actions.rename(item.threadId,text);setNames(previous=>({...previous,[item.threadId]:text}));setEditing(undefined)}:undefined}
    onMenu={(x,y)=>{setMenu({item,x:Math.max(8,Math.min(x,window.innerWidth-190)),y:Math.max(8,Math.min(y,window.innerHeight-200))});setError('')}} onClose={actions&&!archiveView?()=>void archive(item,true):undefined}/>)
  return <div className="session-navigation">
    <div className="session-navigation-scroll" ref={list}>
      {archiveView?<><h2 className="session-section-heading"><Archive size={12} aria-hidden="true"/><span>已归档会话</span></h2>{rows(displayed)}{!loading&&!displayed.length&&<p>暂无归档会话</p>}</>:
        <><h2 className="session-section-heading"><Pin size={12} aria-hidden="true"/><span>置顶会话</span></h2>{rows(displayed.filter(item=>pins.includes(item.threadId)))}<h2 className="session-section-heading"><History size={12} aria-hidden="true"/><span>最近会话</span></h2>{rows(displayed.filter(item=>!pins.includes(item.threadId)))}</>}
      {loading&&<p role="status">正在读取归档会话…</p>}
      {busy&&archiveView&&<p role="status">正在更新会话…</p>}
      {archiveView&&archived?.hasMore&&<button type="button" className="session-archive-entry" disabled={loading} onClick={()=>void loadArchive(archived.nextBeforeThreadId??undefined)}>读取更多归档会话</button>}
    </div>
    {error&&<p role="alert">{error}</p>}
    {actions&&<div className="session-navigation-actions"><button type="button" className="session-archive-entry" onClick={()=>{setArchiveView(value=>!value);setRemoved([]);if(!archiveView)void loadArchive();else{archiveRequest.current++;setLoading(false);setError('')}}}><Archive size={14}/>{archiveView?'返回最近会话':'已归档会话'}</button>
      <SessionCleanup key={archiveView?'archived':'recent'} items={displayed} currentId={currentId} storageKey={storageKey} scopeLabel={archiveView?'归档记录':'未归档记录'} remove={actions.remove} loadItems={actions.history?signal=>actions.history!(archiveView,signal):undefined} onRemoved={ids=>setRemoved(previous=>[...new Set([...previous,...ids])])}/>
    </div>}
    {menu&&createPortal(<div ref={menuElement} className="session-context-menu" role="menu" aria-label="会话操作" style={{left:menu.x,top:menu.y}}>
      <button role="menuitem" disabled={!actions} onClick={()=>{setEditing(menu.item.threadId);setMenu(undefined)}}><Pencil size={14}/>改名</button>
      {!archiveView&&<button role="menuitem" onClick={()=>{toggle(menu.item.threadId);setMenu(undefined)}}><Pin size={14}/>{pins.includes(menu.item.threadId)?'取消置顶':'置顶'}</button>}
      <button role="menuitem" disabled={!actions||busy} onClick={()=>void archive(menu.item,!archiveView)}><Archive size={14}/>{archiveView?'恢复会话':'关闭并归档'}</button>
      <button role="menuitem" className="is-destructive" disabled={!actions||busy} onClick={()=>{setDeleting(menu.item);setMenu(undefined)}}><Trash2 size={14}/>删除</button>
    </div>,document.body)}
    {deleting&&createPortal(<div className="session-delete-backdrop"><div className="session-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="session-delete-title" onKeyDown={event=>{
      if(event.key==='Escape'&&!busy){event.preventDefault();setDeleting(undefined)}
      if(event.key==='Tab'){const buttons=[...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];if(!buttons.length){event.preventDefault();return}const first=buttons[0],last=buttons.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
    }}>
      <h3 id="session-delete-title">删除会话？</h3><p>{sessionName(deleting)}</p><p>会话及对话记录将被删除，无法恢复。已生成文件按存储保留规则处理。</p><div><button autoFocus disabled={busy} onClick={()=>setDeleting(undefined)}>取消</button><button className="is-destructive" disabled={busy} onClick={()=>{if(!actions)return;setBusy(true);setError('');void actions.remove(deleting.threadId).then(()=>{if(!mayUpdate())return;setRemoved(previous=>[...previous,deleting.threadId]);setDeleting(undefined);if(deleting.threadId===currentId)navigateSession(displayed.find(other=>other.threadId!==deleting.threadId)?.threadId??'new')}).catch(()=>setError('删除未完成；运行中的会话需先停止。')).finally(()=>setBusy(false))}}>{busy?'删除中…':'删除'}</button></div>{error&&<p role="alert">{error}</p>}
    </div></div>,document.body)}
  </div>
}
