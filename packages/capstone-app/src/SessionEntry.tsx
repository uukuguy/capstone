import {useEffect,useRef,useState} from 'react'
import './sessionEntry.css'

export type SessionType='grid-analysis'|'enterprise-research'|'general-chat'
export type SessionCreation={session_type:SessionType;model_id?:string}
// Historical sessions retain their stored type and display name.
export const sessionTypeNames:Record<SessionType,string>={'grid-analysis':'电网分析与决策','enterprise-research':'企业研究与分析','general-chat':'通用聊天'}

/** New conversations use one capable path; resources are selected in conversation. */
export default function SessionEntry({onCreate,compact=false}: {
  onCreate:(selection:SessionCreation)=>Promise<void>;compact?:boolean
}) {
  const [busy,setBusy]=useState(true)
  const [error,setError]=useState('')
  const writing=useRef(false),started=useRef(false)
  async function create() {
    if(writing.current)return
    writing.current=true;setBusy(true);setError('')
    try{await onCreate({session_type:'enterprise-research'})}
    catch(cause){setError(cause instanceof Error?cause.message:'会话创建失败，请重试。')}
    finally{writing.current=false;setBusy(false)}
  }
  useEffect(()=>{if(!started.current){started.current=true;void create()}},[])
  return <div className={`session-entry${compact?' is-compact':''}`}>
    {busy&&<p role="status">正在创建会话…</p>}
    {error&&<><p role="alert">{error}</p><button type="button" className="thread-primary-button" disabled={busy} onClick={()=>void create()}>重试创建</button></>}
  </div>
}
