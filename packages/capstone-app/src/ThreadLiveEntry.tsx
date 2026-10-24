import {applicationCapacity} from './applicationCapacity'
import { Activity, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient } from './threadClient'
import { CapstoneClient } from './api'
import { HttpThreadTransport, isThreadVersionError,ThreadTransportError } from './threadHttpTransport'
import ThreadWorkspace from './ThreadWorkspace'
import {ThreadProjectionStore} from './threadProjectionStore'
import {rememberWorkspaceThread,forgetWorkspaceThread} from './workspaceEntry'
import { parseNetworkDiagram } from './networkValidation'
import type { NetworkDiagram } from './types'
import { Plus } from 'lucide-react'
import { rotateStorageNamespace, storageNamespace } from './threadSessionState'
import { readThreadAccess, type ThreadAccessMode } from './threadAccess'
import WorkbenchPreparation from './WorkbenchPreparationView'
import { prepareWorkbench, type PreparationUpdate } from './workbenchPreparation'
import ThreadWorkAdapter from './ThreadWorkAdapter'
import type { ThreadListPage } from './threadManagement'
import SessionNavigation,{SessionAdjacentControls,navigateSession} from './SessionNavigation'
import {sessionManagement} from './sessionManagement'
import {useSessionCatalog,mergeSessionPage} from './sessionCatalog'
import WorkspaceSessionEntry from './WorkspaceSessionEntry'
import SessionNewPopover from './SessionNewPopover'
import {memorySessionLimit,isMemorySessionLimit,readSessionVisits,recordSessionVisit,retainSessions,SessionReadingProvider,type SessionVisits} from './workspaceSessionCache'

const TOKEN_KEY = 'capstone.thread.operatorToken'
const initialPreparation: PreparationUpdate[] = [
  { component: 'api', status: 'preparing' },
  { component: 'database', status: 'waiting' },
  { component: 'worker:pandapower', status: 'waiting' },
  { component: 'worker:pypsa', status: 'waiting' },
]

function readToken(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}

function TokenPrompt({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [value, setValue] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    const token = value.trim()
    if (!token) return
    if (readToken() !== token) rotateStorageNamespace()
    try { sessionStorage.setItem(TOKEN_KEY, token) } catch { /* memory-only fallback */ }
    onSubmit(token)
  }
  return <main className="thread-token-shell">
    <form className="thread-token-card" onSubmit={submit}>
      <span className="eyebrow">CAPSTONE / PRIVATE THREAD</span>
      <h1>连接 Thread</h1>
      <p>输入本地或受信任服务的 operator token。Token 只保存在当前浏览器会话中。</p>
      <label>Operator token<input aria-label="Operator token" type="password" value={value} onChange={(event) => setValue(event.target.value)} autoComplete="off" /></label>
      <button type="submit" disabled={!value.trim()}>连接</button>
    </form>
  </main>
}

export default function ThreadLiveEntry({ threadId, mode, presentation }: { threadId: string; mode?: 'work'; presentation?: 'workspace' }) {
  if (presentation === 'workspace') return <WorkspaceRouteEntry threadId={threadId} />
  return mode === 'work' ? <WorkLiveEntry threadId={threadId} /> : <LegacyThreadLiveEntry threadId={threadId} />
}

function WorkspaceRouteEntry({ threadId }: { threadId: string }) {
  const [currentId, setCurrentId] = useState(threadId)
  const [visited,setVisited]=useState([threadId])
  const [namespace,setNamespace]=useState(()=>storageNamespace(import.meta.env.VITE_API_ORIGIN||''))
  const [limit,setLimit]=useState(memorySessionLimit)
  const recent=useRef([threadId])
  const visits=useRef<SessionVisits>({}),visitsNamespace=useRef('')
  const released=useRef(new Set<string>())
  useEffect(() => {
    if(visitsNamespace.current!==namespace){visits.current=recordSessionVisit(namespace,readSessionVisits(namespace),currentId);visitsNamespace.current=namespace}
    const navigate = () => {
      const id = new URLSearchParams(window.location.search).get('thread')
      if(!id)return
      released.current.delete(id)
      if(id!==currentId)visits.current=recordSessionVisit(namespace,visits.current,id)
      recent.current=retainSessions(recent.current.filter(value=>!released.current.has(value)),id,limit,visits.current)
      // Do not reorder retained DOM: moving an iframe reloads its document.
      setVisited(previous=>[...previous.filter(value=>recent.current.includes(value)),...(!previous.includes(id)?[id]:[])])
      setCurrentId(id)
    }
    const release=(event:Event)=>{
      const id=(event as CustomEvent<string>).detail
      if(typeof id!=='string')return
      released.current.add(id)
      setVisited(previous=>previous.filter(value=>value===currentId||value!==id))
    }
    const resize=(event:Event)=>{
      const n=(event as CustomEvent<number>).detail
      if(!isMemorySessionLimit(n))return
      setLimit(n);recent.current=retainSessions(recent.current,currentId,n,visits.current)
      setVisited(previous=>previous.filter(id=>recent.current.includes(id)))
    }
    const reset=()=>{setNamespace(storageNamespace(import.meta.env.VITE_API_ORIGIN||''));recent.current=[currentId];setVisited([currentId])}
    window.addEventListener('popstate', navigate)
    window.addEventListener('capstone-session-released',release)
    window.addEventListener('capstone-session-cache-limit',resize)
    window.addEventListener('capstone-thread-access-changed',reset)
    return () => {window.removeEventListener('popstate', navigate);window.removeEventListener('capstone-session-released',release);window.removeEventListener('capstone-session-cache-limit',resize);window.removeEventListener('capstone-thread-access-changed',reset)}
  }, [currentId,limit,namespace])
  return <>{visited.map(id=><SessionReadingProvider key={`${namespace}.${id}`} namespace={namespace} threadId={id}><Activity mode={id===currentId?'visible':'hidden'}>
    {id==='new'?<WorkspaceSessionEntry onCreated={navigateSession}/>:<WorkspaceLiveEntry threadId={id}/>}
  </Activity></SessionReadingProvider>)}</>
}

/** Read the host version before choosing a compatible presentation; reads never migrate a Thread. */
function WorkspaceLiveEntry({ threadId }: { threadId: string }) {
  const [token, setToken] = useState(readToken)
  const [resolved, setResolved] = useState<{threadId:string;version:1|2;access:ThreadAccessMode;store:ThreadProjectionStore}|null>(null)
  const [preparing,setPreparing]=useState(true)
  const origin=import.meta.env.VITE_API_ORIGIN||'',namespace=storageNamespace(origin)
  const [sessions,setSessions]=useSessionCatalog(namespace)
  const [needsToken, setNeedsToken] = useState(false)
  const [error, setError] = useState('')
  const [missing,setMissing]=useState(false)
  const [access,setAccess]=useState<ThreadAccessMode>()
  const [retry, setRetry] = useState(0)
  const transition=useRef<HTMLDivElement>(null)
  useEffect(() => {
    // React Activity resumes this effect. The existing adapter owns catch-up;
    // replacing its store would discard the retained reader and preview DOM.
    if(resolved?.threadId===threadId){setPreparing(false);return}
    const controller = new AbortController()
    setError('');setMissing(false);setPreparing(true)
    void readThreadAccess(origin, controller.signal).then(async access => {
      if(controller.signal.aborted)return
      setAccess(access)
      if (access === 'operator' && !token) { if (!controller.signal.aborted) setNeedsToken(true); return }
      const transport=new HttpThreadTransport(origin,access==='open'?'':token,fetch,'/api/v1/threads','2')
      try{const page=await transport.listThreads(false,undefined,controller.signal);if(!controller.signal.aborted)setSessions(previous=>mergeSessionPage(previous,page))}catch{if(controller.signal.aborted)return}
      const readVersion = (version: '1' | '2') => new HttpThreadTransport(origin, access === 'open' ? '' : token, fetch, '/api/v1/threads', version).getSnapshot(threadId, controller.signal)
      let representation: unknown
      try { representation = await readVersion('1') }
      catch (cause) { if (!isThreadVersionError(cause)) throw cause; representation = await readVersion('2') }
      const snapshot = representation as { schema?: unknown; minimum_protocol_version?: unknown }
      if (controller.signal.aborted) return
      const version=snapshot.schema==='capstone-thread-snapshot/1'&&(snapshot.minimum_protocol_version===undefined||snapshot.minimum_protocol_version===1)?1:snapshot.schema==='capstone-thread-snapshot/2'&&snapshot.minimum_protocol_version===2?2:null
      if(!version)throw new Error('会话协议版本暂不支持，请更新应用后重试。')
      const preparedTransport=new HttpThreadTransport(origin,access==='open'?'':token,fetch,'/api/v1/threads',version===2?'2':'1')
      const store=new ThreadProjectionStore(new CapstoneThreadClient(preparedTransport),`${namespace}.${threadId}`,{protocolVersion:version===2?'2':'1'})
      await store.load(threadId)
      if(controller.signal.aborted){store.dispose();return}
      setResolved({threadId,version,access,store});setPreparing(false)
      rememberWorkspaceThread(threadId)
    }).catch(cause => { if (!controller.signal.aborted){setPreparing(false);const notFound=cause instanceof ThreadTransportError&&cause.status===404;setMissing(notFound);if(notFound)forgetWorkspaceThread(threadId);setError(cause instanceof Error ? cause.message : '暂时无法读取会话。')} })
    return () => controller.abort()
  }, [threadId, token, retry])
  if (needsToken && !token) return <TokenPrompt onSubmit={setToken} />
  if (!resolved&&error) return <UnavailableWorkspace message={error} missing={missing} token={access==='open'?'':token} onRetry={()=>setRetry(value=>value+1)} />
  if (!resolved) return <ThreadWorkspace conversationOnly heading={<div className="thread-chat-heading"><h2>工作空间</h2></div>} sidebar={<nav className="thread-session-navigation" aria-label="任务会话"><SessionNewPopover onCreated={navigateSession}/><SessionNavigation items={sessions?.threads??[]} storageKey={namespace}/></nav>}><div className="workspace-preparing" role="status"><span className="spinner"/>正在准备会话…</div></ThreadWorkspace>
  return <div ref={transition} className="workspace-session-transition" data-switching={preparing||!!error||undefined}>
    {resolved.version === 1 ? <LegacyThreadLiveEntry key={resolved.threadId} threadId={resolved.threadId} workspace initialAccess={resolved.access} preparedStore={resolved.store}/> : <WorkLiveEntry threadId={resolved.threadId} recoveryOnly initialAccess={resolved.access} preparedStore={resolved.store}/>}
    {(preparing||error)&&<div className="workspace-transition-overlay" style={{left:window.innerWidth>1100?(transition.current?.querySelector('.workspace-navigation')?.getBoundingClientRect().right??0):0}}>
      <div role={error?'alert':'status'} className="workspace-transition-notice">{error?<><span>{missing?'目标会话不存在或已删除，请选择其他会话。':'目标会话暂未准备好，请重试。'}</span><button onClick={()=>navigateSession(resolved.threadId)}>返回当前会话</button><button onClick={()=>navigateSession('new')}>新建会话</button>{!missing&&<button onClick={()=>setRetry(value=>value+1)}>重试</button>}</>:<><span className="spinner"/>正在切换会话…</>}</div>
    </div>}
  </div>
}

function UnavailableWorkspace({message,missing,token,onRetry}:{message:string;missing:boolean;token:string;onRetry:()=>void}){
  const origin=import.meta.env.VITE_API_ORIGIN||'',namespace=storageNamespace(origin)
  const [sessions,setSessions]=useSessionCatalog(namespace),[revision,setRevision]=useState(0)
  const transport=useMemo(()=>new HttpThreadTransport(origin,token,fetch,'/api/v1/threads','2'),[origin,token])
  useEffect(()=>{const abort=new AbortController();void transport.listThreads(false,undefined,abort.signal).then(page=>{if(!abort.signal.aborted)setSessions(previous=>mergeSessionPage(previous,page))}).catch(()=>{});return()=>abort.abort()},[transport,revision])
  return <ThreadWorkspace conversationOnly heading={<div className="thread-chat-heading"><h2>工作空间</h2></div>}
    sidebar={<nav className="thread-session-navigation" aria-label="任务会话"><SessionNewPopover onCreated={navigateSession}/><SessionNavigation items={sessions?.threads??[]} storageKey={namespace} actions={sessionManagement(transport,()=>setRevision(value=>value+1))}/></nav>}>
    <section className="session-entry" role="alert"><h2>会话暂不可用</h2><p>{missing?'此会话不存在或已删除。请从左侧选择其他会话，或新建会话。':message}</p>
      <button type="button" onClick={()=>navigateSession('new')}>进入新建会话</button><button type="button" onClick={()=>setRevision(value=>value+1)}>刷新会话列表</button>{!missing&&<button type="button" onClick={onRetry}>重新读取会话</button>}
    </section>
  </ThreadWorkspace>
}

function WorkLiveEntry({ threadId, recoveryOnly = false,initialAccess,preparedStore }: { threadId: string; recoveryOnly?: boolean;initialAccess?:ThreadAccessMode;preparedStore?:ThreadProjectionStore }) {
  useEffect(() => {
    if (recoveryOnly) return
    const previousTitle = document.title
    document.title = 'Capstone · 企业任务工作台'
    return () => { document.title = previousTitle }
  }, [recoveryOnly])
  const [token, setToken] = useState(readToken)
  const [access, setAccess] = useState<ThreadAccessMode | null>(initialAccess??null)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const origin = import.meta.env.VITE_API_ORIGIN || ''
  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    void readThreadAccess(origin, controller.signal).then(setAccess).catch(() => {
      if (!controller.signal.aborted) setError('暂时无法连接任务工作台。')
    })
    return () => controller.abort()
  }, [origin, retry])
  const transport = useMemo(() => access === 'open' || (access === 'operator' && token)
    ? new HttpThreadTransport(origin, access === 'open' ? '' : token, fetch, '/api/v1/threads', '2') : null,
  [access, origin, token])
  if (error) return <main className="thread-token-shell"><section className="thread-token-card" role="alert"><p>{error}</p><button onClick={() => setRetry(value => value + 1)}>重新连接</button></section></main>
  if (access === 'operator' && !token) return <TokenPrompt onSubmit={setToken} />
  if (!transport) return <main className="thread-loading" role="status">正在连接任务工作台…</main>
  return <ThreadWorkAdapter transport={transport} threadId={threadId} namespace={storageNamespace(origin)} recoveryOnly={recoveryOnly} preparedStore={preparedStore}/>
}

function LegacyThreadLiveEntry({ threadId, workspace = false,initialAccess,preparedStore }: { threadId: string; workspace?: boolean;initialAccess?:ThreadAccessMode;preparedStore?:ThreadProjectionStore }) {
  const [token, setToken] = useState(readToken)
  const [accessMode, setAccessMode] = useState<ThreadAccessMode | null>(initialAccess??null)
  const [accessError, setAccessError] = useState<string | null>(null)
  const [accessRetry, setAccessRetry] = useState(0)
  const [preparation, setPreparation] = useState<PreparationUpdate[]>(initialPreparation)
  const [createdThreadId, setCreatedThreadId] = useState(threadId === 'new' ? '' : threadId)
  const [creating, setCreating] = useState(threadId === 'new')
  const [error, setError] = useState<string | null>(null)
  const [previewDiagram, setPreviewDiagram] = useState<NetworkDiagram | null>(null)
  const [archived, setArchived] = useState(false)
  const [disabledToolIds, setDisabledToolIds] = useState<string[]>([])
  const [sessionError, setSessionError] = useState(false)
  const [listReload,setListReload]=useState(0)
  const newInFlight = useRef(false)
  const apiOrigin = import.meta.env.VITE_API_ORIGIN || ''
  const prepareConnection = useCallback((signal: AbortSignal, update: (value: PreparationUpdate) => void) =>
    prepareWorkbench(apiOrigin, signal, update), [apiOrigin])
  const hasAccess = accessMode === 'open' || (accessMode === 'operator' && Boolean(token))
  const effectiveToken = accessMode === 'open' ? '' : token
  const transport = useMemo(
    () => hasAccess ? new HttpThreadTransport(apiOrigin, effectiveToken) : null,
    [apiOrigin, effectiveToken, hasAccess],
  )
  const client = useMemo(() => transport ? new CapstoneThreadClient(transport) : null, [transport])
  const creation = useRef<{ client: CapstoneThreadClient; request: ReturnType<CapstoneThreadClient['create']> } | null>(null)
  const authorityClient = useMemo(() => hasAccess ? new CapstoneClient(apiOrigin, effectiveToken) : null, [apiOrigin, effectiveToken, hasAccess])
  const namespace = useMemo(() => hasAccess ? storageNamespace(apiOrigin) : '', [apiOrigin, hasAccess])
  const [sessions,setSessions]=useSessionCatalog(namespace)

  useEffect(() => {
    const refresh=()=>setListReload(value=>value+1)
    window.addEventListener('capstone-session-renamed',refresh)
    return()=>window.removeEventListener('capstone-session-renamed',refresh)
  },[])
  useEffect(() => {
    if (!workspace || !transport) return
    const abort = new AbortController()
    void transport.listThreads(false, undefined, abort.signal).then(page => { if (!abort.signal.aborted) { setSessions(previous=>mergeSessionPage(previous,page)); setSessionError(false) } })
      .catch(() => { if (!abort.signal.aborted) setSessionError(true) })
    return () => abort.abort()
  }, [transport, createdThreadId, workspace,listReload])

  useEffect(() => {
    const abort = new AbortController()
    const timeout = setTimeout(() => abort.abort(), applicationCapacity('ui_prepare_timeout_ms'))
    let active = true
    setAccessError(null)
    setPreparation(initialPreparation)
    void prepareWorkbench(apiOrigin, abort.signal, (update) => {
      if (active) setPreparation(before => before.some(item => item.component === update.component)
        ? before.map(item => item.component === update.component ? update : item) : [...before, update])
    }).then(() => readThreadAccess(apiOrigin, abort.signal)).then((mode) => {
      if (active) setAccessMode(mode)
    }).catch(() => {
      if (active) setAccessError('暂时无法连接工作台，请重试。')
    }).finally(() => clearTimeout(timeout))
    return () => { active = false; clearTimeout(timeout); abort.abort() }
  }, [apiOrigin, accessRetry])

  function selectThread(id: string, push = true) {
    setCreatedThreadId(id); setArchived(false); setError(null); setPreviewDiagram(null)
    if (push) {
      const url = new URL(window.location.href); url.searchParams.set('thread', id)
      window.history.pushState({}, '', url)
    }
  }

  async function newThread() {
    if (!client || newInFlight.current) return
    newInFlight.current = true; setCreating(true); setError(null)
    try {
      const snapshot = await client.create('ieee39')
      selectThread(snapshot.threadId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '新建对话失败') }
    finally { newInFlight.current = false; setCreating(false) }
  }

  useEffect(() => {
    if(workspace)return
    const pop = () => {
      const id = new URLSearchParams(window.location.search).get('thread')
      if (id && id !== 'new') selectThread(id, false)
    }
    window.addEventListener('popstate', pop)
    return () => window.removeEventListener('popstate', pop)
  }, [])

  useEffect(() => {
    if (!transport || !createdThreadId) return
    const abort = new AbortController()
    void transport.getThreadMetadata(createdThreadId, abort.signal).then((metadata) => {
      if (!abort.signal.aborted) {
        setArchived(metadata.archived)
      }
    }).catch(() => { /* Older hosts still enforce command admission themselves. */ })
    return () => abort.abort()
  }, [transport, createdThreadId])

  useEffect(() => {
    if (!client || threadId !== 'new' || createdThreadId) return
    let active = true
    setCreating(true); setError(null)
    // StrictMode replays the effect. Share its request rather than creating
    // a second, unused server Thread for the same entry.
    if (creation.current?.client !== client) creation.current = { client, request: client.create('ieee39') }
    void creation.current.request.then((snapshot) => {
      if (active) {
        setCreatedThreadId(snapshot.threadId)
        const url = new URL(window.location.href)
        url.searchParams.set('thread', snapshot.threadId)
        window.history.replaceState(window.history.state, '', url)
      }
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Thread 创建失败')
    }).finally(() => { if (active) setCreating(false) })
    return () => { active = false }
  }, [client, createdThreadId, threadId])

  useEffect(() => {
    if (!authorityClient || !createdThreadId) return
    let active = true
    void authorityClient.caseDiagram('pandapower-static-analysis', 'pandapower-scripted-task').then((raw) => {
      const diagram = parseNetworkDiagram(raw)
      if (active && diagram) setPreviewDiagram(diagram)
    }).catch(() => {
      // The Thread remains usable when the optional topology preview is unavailable.
    })
    return () => { active = false }
  }, [authorityClient, createdThreadId])

  if (accessError || accessMode === null) return <WorkbenchPreparation updates={preparation} error={accessError}
    onRetry={() => setAccessRetry(value => value + 1)} />
  if (accessMode === 'operator' && !token) return <TokenPrompt onSubmit={setToken} />
  if (error && !createdThreadId) return <main className="thread-token-shell"><div className="thread-token-card" role="alert"><h1>对话暂不可用</h1><p>{error}</p>{accessMode === 'open'
    ? <button type="button" onClick={() => void newThread()}>重试创建</button>
    : <button type="button" onClick={() => { setError(null); setToken('') }}>更换 token</button>}</div></main>
  if (!client || !createdThreadId) return <main className="thread-loading" aria-live="polite"><span className="spinner" />正在创建对话…</main>
  return <ThreadFixtureApp key={createdThreadId} client={client} threadId={createdThreadId}
    preparedStore={preparedStore}
    presentation={workspace ? 'workspace' : undefined}
    navigation={workspace && <nav className="thread-session-navigation" aria-label="任务会话">
      <SessionNewPopover onCreated={navigateSession} />
      <SessionNavigation items={sessions?.threads||[]} currentId={createdThreadId} storageKey={namespace} actions={transport?sessionManagement(transport,change=>{if(change)setSessions(previous=>previous?{...previous,threads:previous.threads.filter(item=>item.threadId!==change.remove)}:null);setListReload(value=>value+1)}):undefined} />
      {sessionError && <p role="status">会话列表暂不可用，当前对话仍可使用。</p>}
    </nav>}
    prepareConnection={prepareConnection}
    disabledToolIds={disabledToolIds} onDisabledToolIdsChange={setDisabledToolIds}
    storageKey={`${namespace}.${createdThreadId}`} readOnly={archived} previewDiagram={previewDiagram}
    workspaceActions={<SessionAdjacentControls items={sessions?.threads||[]} currentId={createdThreadId} storageKey={namespace} />}
    sessionNotice={error} headerActions={workspace ? undefined : <><a className="thread-new-dialogue" href={`/?workspace=enterprise&thread=${encodeURIComponent(createdThreadId)}`}>任务工作台</a><button type="button" className="thread-new-dialogue"
      disabled={creating} onClick={() => void newThread()} aria-label={creating ? '正在新建…' : '新建对话'}>
      <Plus size={16} aria-hidden="true" /><span>{creating ? '正在新建…' : '新建对话'}</span>
    </button></>} />
}
