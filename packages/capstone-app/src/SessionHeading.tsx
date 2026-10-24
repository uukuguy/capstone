import {applicationCapacity} from './applicationCapacity'
import {useState, type ReactNode} from 'react'
import {Pencil} from 'lucide-react'
import './sessionHeading.css'

export default function SessionHeading({title,subtitle,onSave,onSubtitleClick,subtitleAction}:{title:string;subtitle?:string;onSave?:(text:string)=>Promise<void>;onSubtitleClick?:()=>void;subtitleAction?:ReactNode}) {
  const [editing,setEditing]=useState(false),[draft,setDraft]=useState(title),[busy,setBusy]=useState(false),[error,setError]=useState('')
  async function save(){
    if(!draft.trim()){setError('请输入会话名称');return}
    if(!onSave||busy)return
    setBusy(true);setError('')
    try{await onSave(draft.trim());setEditing(false)}catch{setError('名称尚未保存，请重试')}finally{setBusy(false)}
  }
  return <div className="session-heading">
    {editing?<form onSubmit={event=>{event.preventDefault();void save()}}><input autoFocus aria-label="会话名称" maxLength={applicationCapacity('ui_session_title_chars')} value={draft} disabled={busy} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==='Escape'&&!busy){setEditing(false);setError('')}}}/><button type="submit" disabled={busy}>{busy?'保存中':'保存'}</button><button type="button" disabled={busy} onClick={()=>setEditing(false)}>取消</button></form>
      :<div className="session-heading-title"><h2 title={title}>{title}</h2>{onSave&&<button type="button" aria-label="编辑会话名称" onClick={()=>{setDraft(title);setEditing(true);setError('')}}><Pencil size={13}/></button>}</div>}
    {error&&<span role="alert">{error}</span>}{subtitle&&<p className="thread-model-short">{onSubtitleClick?<button type="button" className="session-object-link" onClick={onSubtitleClick}>{subtitle}</button>:subtitle}{subtitleAction}</p>}
  </div>
}
