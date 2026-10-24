import {useEffect,useId,useRef,useState} from 'react'
import {createPortal} from 'react-dom'
import {Plus,X} from 'lucide-react'
import WorkspaceSessionEntry from './WorkspaceSessionEntry'
import './sessionEntry.css'

/** A nonmodal resource picker. The current conversation stays mounted underneath. */
export default function SessionNewPopover({onCreated}:{onCreated?:(id:string)=>void}) {
  const [open,setOpen]=useState(false)
  const [position,setPosition]=useState({left:12,top:64})
  const trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null)
  const id=useId()
  function close(){setOpen(false);trigger.current?.focus({preventScroll:true})}
  useEffect(()=>{
    if(!open)return
    const place=()=>{
      const rect=trigger.current?.getBoundingClientRect()
      if(rect)setPosition({left:Math.max(8,Math.min(rect.left,window.innerWidth-312)),top:Math.max(8,Math.min(rect.bottom+8,window.innerHeight-400))})
    }
    place();panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const outside=(event:PointerEvent)=>{if(!panel.current?.contains(event.target as Node)&&!trigger.current?.contains(event.target as Node))close()}
    let tabTimer:ReturnType<typeof setTimeout>|undefined
    const keyboard=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close()}
      if(event.key==='Tab')tabTimer=setTimeout(()=>{if(!panel.current?.contains(document.activeElement)&&document.activeElement!==trigger.current)setOpen(false)},0)
    }
    document.addEventListener('pointerdown',outside,true)
    document.addEventListener('keydown',keyboard,true)
    window.addEventListener('resize',place)
    return()=>{if(tabTimer)clearTimeout(tabTimer);document.removeEventListener('pointerdown',outside,true);document.removeEventListener('keydown',keyboard,true);window.removeEventListener('resize',place)}
  },[open])
  return <><button ref={trigger} type="button" className="thread-session-new" aria-haspopup="dialog" aria-expanded={open} aria-controls={open?id:undefined} onClick={()=>open?close():setOpen(true)}><Plus size={16} aria-hidden="true"/>新建会话</button>
    {open&&createPortal(<div ref={panel} id={id} role="dialog" aria-label="新建会话" className="session-new-popover" style={position}>
      <div className="session-new-popover-heading"><strong>新建会话</strong><button type="button" aria-label="关闭新建会话" onClick={close}><X size={16} aria-hidden="true"/></button></div>
      <WorkspaceSessionEntry compact onCreated={threadId=>{close();if(onCreated)onCreated(threadId);else window.location.assign(`/?workspace=enterprise&thread=${encodeURIComponent(threadId)}`)}}/>
    </div>,document.body)}
  </>
}
