import {useEffect,useId,useLayoutEffect,useRef,useState} from 'react'
import {createPortal} from 'react-dom'
import {LoaderCircle,Trash2,X} from 'lucide-react'
import {readSessionPins,sessionName,useSessionPins,type SessionNavItem} from './sessionNavigationState'
import './sessionCleanup.css'

export function cleanupCandidates(items:readonly SessionNavItem[],pins:readonly string[],days:number,now:number,currentId?:string){
  if(!Number.isInteger(days)||days<1||days>36500)return []
  const seen=new Set<string>(),cutoff=now-days*86400000
  return items.filter(item=>{
    if(seen.has(item.threadId))return false
    seen.add(item.threadId)
    const created=Date.parse(item.createdAt??'')
    return item.threadId!==currentId&&!pins.includes(item.threadId)&&Number.isFinite(created)&&created<cutoff
  })
}

export default function SessionCleanup({items,storageKey,currentId,scopeLabel,remove,onRemoved,loadItems}:{
  items:readonly SessionNavItem[];storageKey:string;currentId?:string;scopeLabel:string
  remove:(id:string)=>Promise<void>;onRemoved:(ids:string[])=>void
  loadItems?:(signal:AbortSignal)=>Promise<readonly SessionNavItem[]>
}){
  const {pins}=useSessionPins(storageKey)
  const [open,setOpen]=useState(false),[days,setDays]=useState(30),[openedAt,setOpenedAt]=useState(0)
  const [busy,setBusy]=useState(false),[result,setResult]=useState(''),[completed,setCompleted]=useState(false)
  const [progress,setProgress]=useState({done:0,total:0})
  const [inventory,setInventory]=useState<readonly SessionNavItem[]>(items),[loading,setLoading]=useState(false),[loadError,setLoadError]=useState('')
  const request=useRef<AbortController|null>(null)
  const mounted=useRef(true)
  const deleting=useRef(false)
  const anchor=useRef<HTMLButtonElement>(null),popup=useRef<HTMLDivElement>(null),popupId=useId()
  const [position,setPosition]=useState({left:8,bottom:8})
  useEffect(()=>{mounted.current=true;setBusy(deleting.current);return()=>{mounted.current=false;request.current?.abort()}},[])
  function close(restoreFocus=true){request.current?.abort();setOpen(false);if(restoreFocus)anchor.current?.focus({preventScroll:true})}
  useLayoutEffect(()=>{
    if(!open)return
    const place=()=>{const rect=anchor.current?.getBoundingClientRect();if(rect)setPosition({left:Math.max(8,Math.min(rect.left,window.innerWidth-328)),bottom:Math.max(8,window.innerHeight-rect.top+8)})}
    const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!popup.current?.contains(event.target)&&!anchor.current?.contains(event.target))close(false)}
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close()}}
    place();popup.current?.querySelector<HTMLInputElement>('input')?.focus({preventScroll:true})
    document.addEventListener('pointerdown',outside,true);window.addEventListener('keydown',escape,true);window.addEventListener('resize',place)
    return()=>{document.removeEventListener('pointerdown',outside,true);window.removeEventListener('keydown',escape,true);window.removeEventListener('resize',place)}
  },[open])
  async function show(){
    request.current?.abort();const controller=new AbortController();request.current=controller
    setOpenedAt(Date.now());setCompleted(false);setResult('');setLoadError('');setOpen(true)
    setInventory(items);setLoading(Boolean(loadItems))
    if(loadItems)try{
      const loaded=await loadItems(controller.signal)
      if(!controller.signal.aborted)setInventory(loaded)
    }catch{if(!controller.signal.aborted)setLoadError('会话目录未完整读取，未启用删除。')}
    finally{if(!controller.signal.aborted)setLoading(false)}
  }
  const candidates=loading||loadError?[]:cleanupCandidates(inventory,pins,days,openedAt,currentId)
  async function clear(){
    if(deleting.current||busy||completed||!candidates.length)return
    // Freeze exactly the previewed identities; never add later catalog arrivals.
    const targets=[...candidates],deleted:string[]=[]
    const controller=request.current
    let retained=0,failed=0
    deleting.current=true;setBusy(true);setResult('');setProgress({done:0,total:targets.length})
    try{
      for(const item of targets){
        if(controller?.signal.aborted||!mounted.current)break
        const currentPins=readSessionPins(storageKey)
        if(!currentPins){retained+=targets.length-deleted.length-retained-failed;break}
        if(currentPins.includes(item.threadId)){retained++;setProgress({done:deleted.length+retained+failed,total:targets.length});continue}
        try{await remove(item.threadId);deleted.push(item.threadId)}catch{failed++}
        if(!controller?.signal.aborted&&mounted.current)setProgress({done:deleted.length+retained+failed,total:targets.length})
      }
      if(controller?.signal.aborted||!mounted.current)return
      onRemoved(deleted)
      setResult(`已删除 ${deleted.length}${retained?` · 保留 ${retained}`:''}${failed?` · 未删除 ${failed}`:''}`)
      setCompleted(true)
    }finally{deleting.current=false;if(mounted.current)setBusy(false)}
  }
  return <><button ref={anchor} type="button" className="session-cleanup-entry" aria-label="清理会话" aria-haspopup="dialog" aria-expanded={open} aria-controls={open?popupId:undefined} title="按创建时间清理会话" onClick={()=>open?close():void show()}><Trash2 size={14} aria-hidden="true"/><span>清理会话</span></button>
    {open&&createPortal(<div ref={popup} id={popupId} role="dialog" aria-label="清理会话" className="session-cleanup-popover" style={position}>
      <header><strong>清理会话</strong><button type="button" aria-label="关闭清理会话" onClick={()=>close()}><X size={14} aria-hidden="true"/></button></header>
      <p className="session-cleanup-scope">{scopeLabel}{loading?'':` · 共 ${inventory.length} 条`}</p>
      <label className="session-cleanup-age">创建于 <input aria-label="天数" type="number" min="1" max="36500" value={Number.isNaN(days)?'':days} disabled={busy||completed} onChange={event=>setDays(event.target.valueAsNumber)}/> 天前</label>
      <div className="session-cleanup-presets">{[7,30,90].map(value=><button type="button" key={value} aria-pressed={days===value} disabled={busy||completed} onClick={()=>setDays(value)}>{value} 天</button>)}</div>
      <p>置顶和当前会话已排除。删除后无法恢复。</p>
      {loadError&&<p role="alert">{loadError}</p>}
      {loading&&<div className="session-cleanup-loading" role="status" aria-live="polite"><LoaderCircle size={15} aria-hidden="true"/><span>正在查找可清理会话…</span></div>}
      {!completed&&!loading&&!loadError&&<><p>{candidates.length} 个会话将被删除</p><ul className="session-cleanup-preview">{candidates.map(item=><li key={item.threadId}><span>{sessionName(item)}</span><time>{new Date(item.createdAt!).toLocaleDateString('zh-CN')}</time></li>)}</ul></>}
      {result&&<p role="status">{result}</p>}
      <div className="session-cleanup-actions"><button type="button" onClick={()=>close()}>{busy?'停止':completed?'关闭':'取消'}</button>{!completed&&<button type="button" className="session-cleanup-confirm" disabled={loading||busy||!candidates.length} onClick={()=>void clear()}>{loading?'查找中…':busy?`删除中 ${progress.done}/${progress.total}`:`删除 ${candidates.length} 个会话`}</button>}</div>
    </div>,document.body)}
  </>
}
