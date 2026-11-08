import {useState} from 'react'
import type {InputCatalog} from './threadInput'
import type {RuntimeMode} from './threadProtocol'
import type {SessionSkill,SessionSkills} from './sessionSkills'
import './sessionSkillSettings.css'

export default function SessionSkillSettings({value,catalog,mode,onSave,disabled=false}:{value:SessionSkills;catalog?:InputCatalog;mode:RuntimeMode;onSave:(skills:SessionSkill[],revision:number)=>Promise<void>;disabled?:boolean}){
  const [open,setOpen]=useState(false),[draft,setDraft]=useState(value.skills),[revision,setRevision]=useState(value.revision),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const role=mode==='pi_reference'?'direct_pi':'delegated_pi'
  const available=catalog?.resource_profiles[role]?.resources.filter(item=>item.kind==='skill')??[]
  const choices=[...available.map(item=>({id:item.id,version:item.version,role,name:item.native_name||item.id,ready:item.ready})),...draft.filter(item=>!available.some(found=>found.id===item.id)).map(item=>({...item,name:item.id,ready:false}))]
  async function save(){setBusy(true);setError('');try{await onSave(draft,revision);setOpen(false)}catch(cause){setError(cause instanceof Error?cause.message:'会话技能尚未保存。')}finally{setBusy(false)}}
  return <div className="session-skill-settings"><button className="thread-control-button" type="button" disabled={disabled} aria-expanded={open} onClick={()=>{setOpen(!open);setDraft(value.skills);setRevision(value.revision);setError('')}}>会话技能{value.skills.length?` · ${value.skills.length}`:''}</button>
    {open&&<section aria-label="会话技能设置"><p>在本会话中按需使用。单次技能选择仍只对本轮生效；保存后从下一条指令开始应用。</p>
      {choices.map(item=><label key={item.id}><input type="checkbox" checked={draft.some(selected=>selected.id===item.id)} disabled={busy||!item.ready&&!draft.some(selected=>selected.id===item.id)} onChange={event=>setDraft(previous=>event.target.checked?[...previous,{id:item.id,version:item.version,role}]:previous.filter(selected=>selected.id!==item.id))}/>{item.name}{!item.ready?' · 当前不可用，可移除':''}</label>)}
      {!choices.length&&<p>当前没有可选择的会话技能。</p>}
      {error&&<p role="alert">{error}</p>}
      <button type="button" disabled={busy||!catalog} onClick={()=>void save()}>{busy?'保存中':'保存'}</button><button type="button" disabled={busy} onClick={()=>setOpen(false)}>取消</button>
    </section>}
  </div>
}
