import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from 'react'
import {createPortal} from 'react-dom'
import {ArrowDown,ListTree} from 'lucide-react'
import './executionDetails.css'

export const ExecutionDetailsContext=createContext<{target:HTMLDivElement|null;open:()=>void;inlineSummary?:boolean}|null>(null)

/** Locate within the reader without scrolling hidden workspace ancestors. */
export function locateExecutionRecord(reader:HTMLElement,record:HTMLElement){
  reader.dispatchEvent(new Event('execution-browse'))
  reader.scrollTop+=record.getBoundingClientRect().top-reader.getBoundingClientRect().top
  record.focus({preventScroll:true})
}

/** A portal retains the original message runtime and its tool/answer components. */
export function ExecutionDetailEntry({id,label,status,children,enabled=true}:{id:string;label:string;status:string;children:ReactNode;enabled?:boolean}){
  const dock=useContext(ExecutionDetailsContext)
  const record=useRef<HTMLElement>(null)
  if(!enabled||!dock?.target)return <>{children}</>
  const locate=()=>{
    dock.target!.dispatchEvent(new Event('execution-browse'))
    dock.open()
    requestAnimationFrame(()=>{
      if(record.current)locateExecutionRecord(dock.target!,record.current)
    })
  }
  return <>
    <div className="execution-receipt"><span>{status}</span><button type="button" onClick={locate}><ListTree aria-hidden="true"/>查看执行详情</button></div>
    {createPortal(<section ref={record} tabIndex={-1} className="execution-detail-entry" data-execution-id={id} aria-label={label||'执行记录'}>
      <header className="execution-detail-heading"><strong title={label}>执行 · {label||'本次执行'}</strong><span>{status}</span></header>
      <div className="execution-detail-content">{children}</div>
    </section>,dock.target,id)}
  </>
}

export function ExecutionDetailsSurface({onTarget}:{onTarget:(node:HTMLDivElement|null)=>void}){
  const [node,setNode]=useState<HTMLDivElement|null>(null)
  const following=useRef(true)
  const [manual,setManual]=useState(false)
  const [updated,setUpdated]=useState(false)
  useEffect(()=>{onTarget(node);return()=>onTarget(null)},[node,onTarget])
  useEffect(()=>{
    if(!node)return
    const browse=()=>{following.current=false;setManual(true)}
    node.addEventListener('execution-browse',browse)
    const observer=new MutationObserver(()=>{
      if(following.current){if(node.clientHeight)node.scrollTop=node.scrollHeight}
      else setUpdated(true)
    })
    observer.observe(node,{childList:true,subtree:true,characterData:true})
    const resize=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(()=>{
      if(following.current&&node.clientHeight)node.scrollTop=node.scrollHeight
    })
    resize?.observe(node)
    return()=>{observer.disconnect();resize?.disconnect();node.removeEventListener('execution-browse',browse)}
  },[node])
  return <div className="execution-details-surface">
    <div className="execution-details-toolbar">{manual&&<button type="button" onClick={()=>{
      following.current=true;setManual(false);setUpdated(false)
      if(node)node.scrollTop=node.scrollHeight
    }}><ArrowDown aria-hidden="true"/>{updated?'有更新 · 回到当前':'回到当前'}</button>}</div>
    <div ref={setNode} className="execution-details-records" aria-label="执行详情记录" onScroll={()=>{
      if(!node?.clientHeight)return
      const atEnd=node.scrollHeight-node.clientHeight-node.scrollTop<24
      following.current=atEnd;setManual(!atEnd)
      if(atEnd)setUpdated(false)
    }}/>
  </div>
}
