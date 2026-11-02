import {useEffect,useRef,useState} from 'react'
import SessionEntry,{type SessionCreation} from './SessionEntry'
import SessionNavigation,{navigateSession} from './SessionNavigation'
import {sessionManagement} from './sessionManagement'
import {useSessionCatalog,mergeSessionPage} from './sessionCatalog'
import {storageNamespace} from './threadSessionState'
import ThreadWorkspace from './ThreadWorkspace'
import {HttpThreadTransport,ThreadTransportError} from './threadHttpTransport'
import {readThreadAccess} from './threadAccess'
import {currentWorkspaceName,isWorkspaceActive} from './workspaceName'
import {readLastWorkspaceThread,forgetWorkspaceThread} from './workspaceEntry'

export default function WorkspaceSessionEntry({onCreated,compact=false}:{onCreated:(id:string)=>void;compact?:boolean}) {
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
  const workspaceName=currentWorkspaceName()
  const namespace=storageNamespace(origin),[sessions,setSessions]=useSessionCatalog(namespace)
  useEffect(()=>{
    const controller=new AbortController()
    setReady(false);setError('')
    void readThreadAccess(origin,controller.signal).then(async access=>{
      if(access==='operator'&&!token){setNeedsToken(true);return}
      const auth=access==='open'?'':token
      const sessionTransport=new HttpThreadTransport(origin,auth,fetch,'/api/v1/threads','1',workspaceName)
      setTransport(sessionTransport)
      if(!compact&&!new URLSearchParams(window.location.search).has('thread')) {
        const saved=readLastWorkspaceThread(workspaceName),seen=new Set<string>()
        let before:string|undefined,recent:string|undefined
        while(!controller.signal.aborted) {
          const page=await sessionTransport.listThreads(false,before,controller.signal)
          if(controller.signal.aborted||!isWorkspaceActive(workspaceName)||new URLSearchParams(window.location.search).has('thread'))return
          setSessions(previous=>mergeSessionPage(previous,page))
          recent??=page.threads.find(item=>!item.archived)?.threadId
          if(saved&&page.threads.some(item=>item.threadId===saved&&!item.archived)){navigateSession(saved);return}
          if(!saved||!page.hasMore){
            if(saved)forgetWorkspaceThread(saved,workspaceName)
            if(recent){navigateSession(recent);return}
            break
          }
          const next=page.nextBeforeThreadId
          if(!next||seen.has(next))throw new Error('会话目录未完整读取，请重试。')
          seen.add(next);before=next
        }
      } else if(!compact) {
        void sessionTransport.listThreads(false,undefined,controller.signal).then(page=>{
          if(!controller.signal.aborted)setSessions(previous=>mergeSessionPage(previous,page))
        }).catch(()=>{/* Existing history remains available if refresh fails. */})
      }
      if(controller.signal.aborted)return
      setTransport(sessionTransport);setCreationToken(auth);setReady(true)
    }).catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error&&cause.message?cause.message:'暂时无法连接，请重试。')})
    return()=>controller.abort()
  },[origin,token,retry,compact])
  async function create(selection:SessionCreation) {
    if(!transport)throw new Error('请先连接会话服务。')
    const version='2'
    let body:{schema?:string;thread_id?:string}
    try {
      body=await new HttpThreadTransport(origin,creationToken,fetch,'/api/v1/threads',version,workspaceName).createSession(selection) as typeof body
    } catch(cause) {
      if(mounted.current&&creationToken&&cause instanceof ThreadTransportError&&cause.status===401){
        sessionStorage.removeItem('capstone.thread.operatorToken')
        setNeedsToken(true);setReady(false);setToken('')
      }
      throw cause
    }
    if(!body||body.schema!==`capstone-thread-snapshot/${version}`||typeof body.thread_id!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(body.thread_id))throw new Error('会话创建响应无效，请重新读取会话列表。')
    if(mounted.current&&isWorkspaceActive(workspaceName))onCreated(body.thread_id)
  }
  const content=needsToken&&!token?<form className="session-entry" onSubmit={event=>{event.preventDefault();const value=new FormData(event.currentTarget).get('token');if(typeof value==='string'&&value.trim()){sessionStorage.setItem('capstone.thread.operatorToken',value.trim());setToken(value.trim())}}}><label>Operator token<input name="token" type="password" autoComplete="off" required /></label><button type="submit">连接</button></form>
      :error?<div className="session-entry" role="alert"><p>{error}</p><button type="button" onClick={()=>setRetry(value=>value+1)}>重试连接</button></div>
      :ready?<SessionEntry compact={compact} onCreate={create} />:<p role="status">正在连接会话服务…</p>
  if(compact)return content
  return <ThreadWorkspace conversationOnly heading={<div className="thread-chat-heading"><h2>新建任务会话</h2></div>}
    sidebar={<nav className="thread-session-navigation" aria-label="任务会话"><button type="button" className="thread-session-new" onClick={()=>navigateSession('new')}>新建会话</button>
      <SessionNavigation items={sessions?.threads||[]} storageKey={namespace} actions={transport?sessionManagement(transport,change=>{if(change)setSessions(previous=>previous?{...previous,threads:previous.threads.filter(item=>item.threadId!==change.remove)}:null);setRetry(value=>value+1)}):undefined}/>
    </nav>}>
    {content}
  </ThreadWorkspace>
}
