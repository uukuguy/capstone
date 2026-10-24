import {useRef,useState} from 'react'
import type {ThreadCatalogModel} from './threadCatalog'
import './sessionEntry.css'

export type SessionType='grid-analysis'|'enterprise-research'|'general-chat'
export type SessionCreation={session_type:SessionType;model_id?:string}
export const sessionTypeNames:Record<SessionType,string>={'grid-analysis':'电网分析与决策','enterprise-research':'企业研究与分析','general-chat':'通用聊天'}

/** Select initial resources. The existing conversation owns all subsequent instructions. */
export default function SessionEntry({models,onCreate,loading=false,compact=false}: {
  models:readonly ThreadCatalogModel[];onCreate:(selection:SessionCreation)=>Promise<void>;loading?:boolean;compact?:boolean
}) {
  const [type,setType]=useState<SessionType>('general-chat')
  const [model,setModel]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const writing=useRef(false)
  const validModel=models.some(item=>item.modelId===model&&item.available!==false)
  const [chooseModel,setChooseModel]=useState(false)
  async function create(selected:SessionType) {
    if(writing.current||loading||(selected==='grid-analysis'&&!validModel))return
    writing.current=true;setBusy(true);setError('')
    try{await onCreate({session_type:selected,...(selected==='grid-analysis'?{model_id:model}:{})})}
    catch(cause){setError(cause instanceof Error?cause.message:'会话创建失败，请重试。')}
    finally{writing.current=false;setBusy(false)}
  }
  return <form className={`session-entry${compact?' is-compact':''}`} onSubmit={event=>{event.preventDefault();void create(type)}}>
    {compact?<div className="session-entry-options">
      {(Object.keys(sessionTypeNames) as SessionType[]).map(item=><button type="button" key={item} disabled={busy||loading} aria-label={sessionTypeNames[item]} aria-expanded={item==='grid-analysis'?chooseModel:undefined} onClick={()=>{setType(item);setError('');if(item==='grid-analysis')setChooseModel(true);else void create(item)}}>
        <strong>{sessionTypeNames[item]}</strong><small>{item==='general-chat'?'直接讨论问题':item==='enterprise-research'?'创建后可上传研究资料':'选择已注册模型'}</small>
      </button>)}
    </div>:<><p>选择会话的初始资源，具体目标可在对话中逐步明确。</p>
    <fieldset disabled={busy}><legend>会话类型</legend>
      {(Object.keys(sessionTypeNames) as SessionType[]).map(item=><label key={item} className="session-entry-choice"><input type="radio" name="session-type" checked={type===item} onChange={()=>setType(item)} /><span>{sessionTypeNames[item]}</span></label>)}
    </fieldset></>}
    {type==='grid-analysis'&&(!compact||chooseModel)&&<label className="session-entry-model">主要模型<select autoFocus={compact} aria-label="主要模型" value={model} disabled={busy||loading} onChange={event=>setModel(event.target.value)}><option value="">{loading?'正在读取注册模型…':'选择注册模型'}</option>{models.map(item=><option key={item.modelId} value={item.modelId} disabled={item.available===false}>{item.displayName}{item.available===false?'（暂不可用）':''}</option>)}</select></label>}
    {!compact&&type==='enterprise-research'&&<p>以对话开展研究；文档和授权资源接入后再按需选择。</p>}
    {!compact&&type==='general-chat'&&<p>不绑定专业模型，直接讨论问题并持续追问。</p>}
    {error&&<p role="alert">{error}</p>}
    {(!compact||chooseModel&&type==='grid-analysis')&&<button className="thread-primary-button" type="submit" disabled={busy||(type==='grid-analysis'&&(loading||!validModel))}>{busy?'正在创建…':'创建会话'}</button>}
    {compact?busy&&<p role="status">正在创建会话…</p>:<p className="session-entry-note">创建会话不会执行任务。进入后发送第一条消息即可开始，不需要另行启动。</p>}
  </form>
}
