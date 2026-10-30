import {useEffect,useRef,useState} from 'react'
import {MoreHorizontal,Trash2,X} from 'lucide-react'
import {applicationCapacity} from './applicationCapacity'
import {workspaceThreadUrl} from './workspaceName'
import {navigateSession,sessionName,type SessionNavItem} from './sessionNavigationState'
const updatedTimeFormat=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23',timeZoneName:'shortOffset'})

export default function SessionRow({item,current,editing,onEdit,onRename,onMenu,onClose,onDelete,onActivate}: {
  item:SessionNavItem;current:boolean;editing:boolean;onEdit:()=>void;onRename?:(text:string)=>Promise<void>;
  onMenu:(x:number,y:number)=>void;onClose?:()=>void;onDelete?:()=>void;
  onActivate?:()=>void;
}) {
  const [draft,setDraft]=useState(sessionName(item)),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const link=useRef<HTMLAnchorElement>(null),timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined)
  useEffect(()=>()=>{clearTimeout(timer.current)},[])
  async function save(){if(!draft.trim()||!onRename||busy)return;setBusy(true);setError('');try{await onRename(draft.trim())}catch{setError('名称未保存，请重试')}finally{setBusy(false)}}
  const updated=item.updatedAt&&Number.isFinite(Date.parse(item.updatedAt))?updatedTimeFormat.format(new Date(item.updatedAt)):'暂无记录'
  return <div className="session-navigation-row" data-selected={current||undefined} onContextMenu={event=>{event.preventDefault();onMenu(event.clientX,event.clientY)}}
    onKeyDown={event=>{if(event.key==='ContextMenu'||event.shiftKey&&event.key==='F10'){event.preventDefault();const r=event.currentTarget.getBoundingClientRect();onMenu(r.left+16,r.top+24)}}}>
    {editing?<form onSubmit={event=>{event.preventDefault();void save()}}><input autoFocus aria-label="会话名称" maxLength={applicationCapacity('ui_session_title_chars')} disabled={busy} value={draft} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();if(!busy){setDraft(sessionName(item));onEdit();setError('');link.current?.focus()}}}}/><button type="submit" disabled={busy} aria-label="保存会话名称">保存</button>{error&&<span role="alert">{error}</span>}</form>:
      <a ref={link} aria-current={current?'page':undefined} aria-label={`${sessionName(item)}${item.modelId?` · ${item.modelId}`:''}`} title={`${sessionName(item)}${item.modelId?` · ${item.modelId}`:''} · ${item.threadId}\n最后更新：${updated}`} href={workspaceThreadUrl(item.threadId)}
        onDoubleClick={event=>{if(!onRename)return;event.preventDefault();clearTimeout(timer.current);setDraft(sessionName(item));onEdit()}}
        onClick={event=>{
          if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return
          event.preventDefault();clearTimeout(timer.current)
          // Keep the DOM in place long enough to distinguish double-click rename.
          const activate=()=>onActivate?onActivate():navigateSession(item.threadId)
          if(event.detail>0&&onRename)timer.current=setTimeout(activate,220)
          else activate()
        }}><span>{sessionName(item)}{item.modelId&&<small> · {item.modelId}</small>}</span></a>}
    {!editing&&<span className="session-row-actions">
      <button type="button" className="session-row-menu" aria-label={`会话操作：${sessionName(item)}`} title="会话操作" onClick={event=>{const r=event.currentTarget.getBoundingClientRect();onMenu(r.left,r.bottom)}}><MoreHorizontal size={14}/></button>
      {onClose&&<button type="button" aria-label={`关闭会话：${sessionName(item)}`} title="关闭并归档" onClick={onClose}><X size={13}/></button>}
      {onDelete&&<button type="button" aria-label={`删除会话：${sessionName(item)}`} title="删除会话" onClick={onDelete}><Trash2 size={13}/></button>}
    </span>}
  </div>
}
