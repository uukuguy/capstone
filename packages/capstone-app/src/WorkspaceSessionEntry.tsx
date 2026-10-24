import {useEffect,useRef,useState} from 'react'
import SessionEntry,{type SessionCreation} from './SessionEntry'
import SessionNavigation,{navigateSession} from './SessionNavigation'
import {sessionManagement} from './sessionManagement'
import {useSessionCatalog,mergeSessionPage} from './sessionCatalog'
import {storageNamespace} from './threadSessionState'
import ThreadWorkspace from './ThreadWorkspace'
import {HttpThreadTransport} from './threadHttpTransport'
import {readThreadAccess} from './threadAccess'
import {parseThreadCatalog,type ThreadCatalog} from './threadCatalog'
import type {ThreadListPage} from './threadManagement'

export default function WorkspaceSessionEntry({onCreated,compact=false}:{onCreated:(id:string)=>void;compact?:boolean}) {
  const [catalog,setCatalog]=useState<ThreadCatalog>()
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const [ready,setReady]=useState(false)
  const [token,setToken]=useState(()=>sessionStorage.getItem('capstone.thread.operatorToken')||'')
  const [needsToken,setNeedsToken]=useState(false)
  const [transport,setTransport]=useState<HttpThreadTransport>()
  const [creationToken,setCreationToken]=useState('')
  const mounted=useRef(false)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
  const origin=import.meta.env.VITE_API_ORIGIN||''
  const namespace=storageNamespace(origin),[sessions,setSessions]=useSessionCatalog(namespace)
  useEffect(()=>{
    const controller=new AbortController()
    setReady(false);setError('')
    void readThreadAccess(origin,controller.signal).then(async access=>{
      if(access==='operator'&&!token){setNeedsToken(true);return}
      const auth=access==='open'?'':token
      const sessionTransport=new HttpThreadTransport(origin,auth)
      setTransport(sessionTransport)
      if(!compact) {
        try {
          const page=await sessionTransport.listThreads(false,undefined,controller.signal)
          if(controller.signal.aborted)return
          setSessions(previous=>mergeSessionPage(previous,page))
        } catch { if(controller.signal.aborted)return }
      }
      const next=parseThreadCatalog(await sessionTransport.getSessionCatalog(controller.signal))
      if(controller.signal.aborted)return
      setCatalog(next);setTransport(sessionTransport);setCreationToken(auth);setReady(true)
    }).catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'暂时无法连接，请重试。')})
    return()=>controller.abort()
  },[origin,token,retry,compact])
  async function create(selection:SessionCreation) {
    if(!transport)throw new Error('请先连接会话服务。')
    const version=selection.session_type==='grid-analysis'?'1':'2'
    const body=await new HttpThreadTransport(origin,creationToken,fetch,'/api/v1/threads',version).createSession(selection) as {schema?:string;thread_id?:string}
    if(!body||body.schema!==`capstone-thread-snapshot/${version}`||typeof body.thread_id!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(body.thread_id))throw new Error('会话创建响应无效，请重新读取会话列表。')
    if(mounted.current)onCreated(body.thread_id)
  }
  const content=needsToken&&!token?<form className="session-entry" onSubmit={event=>{event.preventDefault();const value=new FormData(event.currentTarget).get('token');if(typeof value==='string'&&value.trim()){sessionStorage.setItem('capstone.thread.operatorToken',value.trim());setToken(value.trim())}}}><label>Operator token<input name="token" type="password" autoComplete="off" required /></label><button type="submit">连接</button></form>
      :error?<div className="session-entry" role="alert"><p>{error}</p><button type="button" onClick={()=>setRetry(value=>value+1)}>重新读取资源</button></div>
      :ready?<SessionEntry compact={compact} models={catalog?.models||[]} onCreate={create} />:<p role="status">正在读取会话资源…</p>
  if(compact)return content
  return <ThreadWorkspace conversationOnly heading={<div className="thread-chat-heading"><h2>新建任务会话</h2></div>}
    sidebar={<nav className="thread-session-navigation" aria-label="任务会话"><button type="button" className="thread-session-new" onClick={()=>navigateSession('new')}>新建会话</button>
      <SessionNavigation items={sessions?.threads||[]} storageKey={namespace} actions={transport?sessionManagement(transport,change=>{if(change)setSessions(previous=>previous?{...previous,threads:previous.threads.filter(item=>item.threadId!==change.remove)}:null);setRetry(value=>value+1)}):undefined}/>
    </nav>}>
    {content}
  </ThreadWorkspace>
}
