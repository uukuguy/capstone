import {useState,useId,useRef,useEffect} from 'react'
import type {InputCatalog} from './threadInput'
import type {RuntimeMode} from './threadProtocol'
import type {SessionSkill,SessionSkills} from './sessionSkills'
import './sessionSkillSettings.css'

export default function SessionSkillSettings({value,catalog,mode,onSave,onReload,disabled=false}:{value:SessionSkills;catalog?:InputCatalog;mode:RuntimeMode;onSave:(skills:SessionSkill[],revision:number)=>Promise<void>;onReload?:()=>Promise<SessionSkills>;disabled?:boolean}){
  const [open,setOpen]=useState(false),[draft,setDraft]=useState(value.skills),[revision,setRevision]=useState(value.revision),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),panelId=useId()
  const role=mode==='pi_reference'?'direct_pi':'delegated_pi'
  const profile=catalog?.resource_profiles[role]
  const available=profile?.resources.filter(item=>item.kind==='skill')??[]
  const choices=[...available.map(item=>({id:item.id,version:item.version,role,loaded_identity:item.loaded_identity||undefined,catalog_revision:profile!.revision,native_name:item.native_name||item.id,name:item.native_name||item.id,ready:item.ready&&!!item.loaded_identity})),...draft.filter(item=>!available.some(found=>found.id===item.id)).map(item=>({...item,name:item.id,ready:false}))]
  const currentChoice=(skill:SessionSkill)=>choices.some(item=>item.id===skill.id&&item.ready&&item.role===skill.role&&item.version===skill.version&&!!skill.loaded_identity&&item.loaded_identity===skill.loaded_identity)
  const needsReselection=draft.some(skill=>!currentChoice(skill))
  useEffect(()=>{
    if(!open)return
    const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target))setOpen(false)}
    document.addEventListener('pointerdown',outside)
    return()=>document.removeEventListener('pointerdown',outside)
  },[open])
  function close(){setOpen(false);trigger.current?.focus()}
  async function save(){setBusy(true);setError('');try{await onSave(draft,revision);setOpen(false)}catch(cause){setError(cause instanceof Error?cause.message:'会话技能尚未保存。')}finally{setBusy(false)}}
  async function reload(){if(!onReload)return;setBusy(true);setError('');try{const latest=await onReload();setDraft(latest.skills);setRevision(latest.revision);setNotice('已读取最新配置，请重新选择后保存。')}catch(cause){setError(cause instanceof Error?cause.message:'会话配置尚未读取。')}finally{setBusy(false)}}
  return <div ref={root} className="session-skill-settings" onKeyDown={event=>{if(event.key==='Escape'&&open&&!busy){event.preventDefault();event.stopPropagation();close()}}}><button ref={trigger} className="thread-settings-item" type="button" disabled={disabled||busy} aria-expanded={open} aria-controls={panelId} onClick={()=>{setOpen(!open);setDraft(value.skills);setRevision(value.revision);setError('');setNotice('')}}>会话技能{value.skills.length?` · ${value.skills.length}`:''}</button>
    {open&&<section id={panelId} aria-label="会话技能设置"><p>默认自动选择适用方法，无需配置。可在这里设置本会话的偏好；保存后从下一条指令开始应用。</p>
      {choices.map(item=><label key={item.id}><input type="checkbox" checked={draft.some(selected=>selected.id===item.id)} disabled={busy||!item.ready&&!draft.some(selected=>selected.id===item.id)} onChange={event=>setDraft(previous=>event.target.checked?[...previous,{id:item.id,version:item.version,role,loaded_identity:item.loaded_identity!,native_name:item.native_name||item.id,catalog_revision:item.catalog_revision!}]:previous.filter(selected=>selected.id!==item.id))}/>{item.name}{!item.ready?' · 当前不可用，可移除':''}</label>)}
      {!choices.length&&<p>当前没有可选择的会话技能。</p>}
      {needsReselection&&<p role="status">已选方法的内容或适用角色未确认，请读取最新配置，移除后重新选择。</p>}
      {notice&&<p role="status">{notice}</p>}
      {error&&<p role="alert">{error}</p>}
      {onReload&&<button type="button" disabled={busy} onClick={()=>void reload()}>读取最新配置</button>}
      <button type="button" disabled={busy||!catalog||needsReselection} onClick={()=>void save()}>{busy?'保存中':'保存'}</button><button type="button" disabled={busy} onClick={close}>取消</button>
    </section>}
  </div>
}
