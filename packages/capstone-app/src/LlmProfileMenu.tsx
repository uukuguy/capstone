import {useEffect,useRef,useState} from 'react'
import {Check,ChevronDown,Server} from 'lucide-react'
import type {InputCatalog} from './threadInput'

type Catalog=NonNullable<InputCatalog['llm_profiles']>
function Icon({kind}:{kind?:string}) {
  return kind==='deepseek'?<img src="/icons/deepseek.svg" alt="" aria-hidden="true"/>:<Server aria-hidden="true"/>
}
function label(profile:Catalog['profiles'][number]) {
  return profile.label===profile.model||!profile.model?profile.label:`${profile.label} · ${profile.model}`
}
export default function LlmProfileMenu({catalog,value,disabled,onChange}:{catalog?:Catalog;value?:string;disabled?:boolean;onChange:(id:string)=>void}) {
  const [open,setOpen]=useState(false)
  const root=useRef<HTMLDivElement>(null)
  const trigger=useRef<HTMLButtonElement>(null)
  const selected=catalog?.profiles.find(p=>p.id===(value??catalog.default_profile_id))
  useEffect(()=>{
    if(!open)return
    const close=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target))setOpen(false)}
    document.addEventListener('pointerdown',close)
    root.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"][aria-checked="true"]:not(:disabled), [role="menuitemradio"]:not(:disabled)')?.focus()
    return ()=>document.removeEventListener('pointerdown',close)
  },[open])
  useEffect(()=>{if(disabled)setOpen(false)},[disabled])
  return <div className="thread-llm-selector" ref={root} onKeyDown={event=>{
    if(event.key==='Escape'){event.stopPropagation();setOpen(false);trigger.current?.focus()}
    if(event.key==='Tab')setOpen(false)
    if(open&&['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault()
      const items=Array.from(root.current!.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]:not(:disabled)'))
      const index=items.indexOf(document.activeElement as HTMLButtonElement)
      items[event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus()
    }
  }}>
    <button ref={trigger} type="button" className="thread-settings-trigger" aria-label="后端 LLM" aria-haspopup="menu" aria-expanded={open} disabled={disabled||!catalog} title="本会话后续指令使用的 LLM" onClick={()=>setOpen(!open)}>
      <Icon kind={selected?.icon}/><span>{selected?label(selected):catalog?'已选 LLM 不可用':'LLM 目录加载中'}</span><ChevronDown aria-hidden="true"/>
    </button>
    {open&&<div role="menu" aria-label="后端 LLM 选项" className="thread-llm-popover">{catalog?.profiles.map(profile=><button type="button" role="menuitemradio" aria-checked={selected?.id===profile.id} disabled={!profile.available} key={profile.id} onClick={()=>{onChange(profile.id);setOpen(false);trigger.current?.focus()}}>
      <Icon kind={profile.icon}/><span>{label(profile)}{!profile.available&&<small>未配置</small>}</span><Check aria-hidden="true" style={{visibility:selected?.id===profile.id?'visible':'hidden'}}/>
    </button>)}</div>}
  </div>
}
