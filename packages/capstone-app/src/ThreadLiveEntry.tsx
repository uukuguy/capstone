import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient } from './threadClient'
import { CapstoneClient } from './api'
import { HttpThreadTransport, isThreadVersionError } from './threadHttpTransport'
import { parseNetworkDiagram } from './networkValidation'
import type { NetworkDiagram } from './types'
import { Plus } from 'lucide-react'
import { rotateStorageNamespace, storageNamespace } from './threadSessionState'
import { readThreadAccess, type ThreadAccessMode } from './threadAccess'
import WorkbenchPreparation from './WorkbenchPreparationView'
import { prepareWorkbench, type PreparationUpdate } from './workbenchPreparation'
import ThreadWorkAdapter from './ThreadWorkAdapter'
import type { ThreadListPage } from './threadManagement'

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
  useEffect(() => {
    const navigate = () => { const id = new URLSearchParams(window.location.search).get('thread'); if (id) setCurrentId(id) }
    window.addEventListener('popstate', navigate)
    return () => window.removeEventListener('popstate', navigate)
  }, [])
  return currentId === 'new' ? <LegacyThreadLiveEntry key={currentId} threadId={currentId} workspace /> : <WorkspaceLiveEntry key={currentId} threadId={currentId} />
}

/** Read the host version before choosing a compatible presentation; reads never migrate a Thread. */
function WorkspaceLiveEntry({ threadId }: { threadId: string }) {
  const [token, setToken] = useState(readToken)
  const [version, setVersion] = useState<1 | 2 | null>(null)
  const [needsToken, setNeedsToken] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setVersion(null); setError('')
    const origin = import.meta.env.VITE_API_ORIGIN || ''
    void readThreadAccess(origin, controller.signal).then(async access => {
      if (access === 'operator' && !token) { if (!controller.signal.aborted) setNeedsToken(true); return }
      const readVersion = (version: '1' | '2') => new HttpThreadTransport(origin, access === 'open' ? '' : token, fetch, '/api/v1/threads', version).getSnapshot(threadId, controller.signal)
      let representation: unknown
      try { representation = await readVersion('1') }
      catch (cause) { if (!isThreadVersionError(cause)) throw cause; representation = await readVersion('2') }
      const snapshot = representation as { schema?: unknown; minimum_protocol_version?: unknown }
      if (controller.signal.aborted) return
      if (snapshot.schema === 'capstone-thread-snapshot/1' && (snapshot.minimum_protocol_version === undefined || snapshot.minimum_protocol_version === 1)) setVersion(1)
      else if (snapshot.schema === 'capstone-thread-snapshot/2' && snapshot.minimum_protocol_version === 2) setVersion(2)
      else throw new Error('会话协议版本暂不支持，请更新应用后重试。')
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '暂时无法读取会话。') })
    return () => controller.abort()
  }, [threadId, token, retry])
  if (needsToken && !token) return <TokenPrompt onSubmit={setToken} />
  if (error) return <main className="thread-token-shell"><section role="alert"><p>{error}</p><button onClick={() => setRetry(value => value + 1)}>重新读取会话</button></section></main>
  if (!version) return <main className="thread-loading" role="status">正在恢复会话…</main>
  return version === 1 ? <LegacyThreadLiveEntry threadId={threadId} workspace /> : <WorkLiveEntry threadId={threadId} recoveryOnly />
}

function WorkLiveEntry({ threadId, recoveryOnly = false }: { threadId: string; recoveryOnly?: boolean }) {
  const [token, setToken] = useState(readToken)
  const [access, setAccess] = useState<ThreadAccessMode | null>(null)
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
  return <ThreadWorkAdapter transport={transport} threadId={threadId} namespace={storageNamespace(origin)} recoveryOnly={recoveryOnly} />
}

function LegacyThreadLiveEntry({ threadId, workspace = false }: { threadId: string; workspace?: boolean }) {
  const [token, setToken] = useState(readToken)
  const [accessMode, setAccessMode] = useState<ThreadAccessMode | null>(null)
  const [accessError, setAccessError] = useState<string | null>(null)
  const [accessRetry, setAccessRetry] = useState(0)
  const [preparation, setPreparation] = useState<PreparationUpdate[]>(initialPreparation)
  const [createdThreadId, setCreatedThreadId] = useState(threadId === 'new' ? '' : threadId)
  const [creating, setCreating] = useState(threadId === 'new')
  const [error, setError] = useState<string | null>(null)
  const [previewDiagram, setPreviewDiagram] = useState<NetworkDiagram | null>(null)
  const [archived, setArchived] = useState(false)
  const [disabledToolIds, setDisabledToolIds] = useState<string[]>([])
  const [sessions, setSessions] = useState<ThreadListPage | null>(null)
  const [sessionError, setSessionError] = useState(false)
  const [listingMore, setListingMore] = useState(false)
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

  useEffect(() => {
    if (!workspace || !transport) return
    const abort = new AbortController()
    void transport.listThreads(false, undefined, abort.signal).then(page => { if (!abort.signal.aborted) { setSessions(page); setSessionError(false) } })
      .catch(() => { if (!abort.signal.aborted) setSessionError(true) })
    return () => abort.abort()
  }, [transport, createdThreadId, workspace])

  useEffect(() => {
    const abort = new AbortController()
    const timeout = setTimeout(() => abort.abort(), 180000)
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
    presentation={workspace ? 'workspace' : undefined}
    navigation={workspace && <nav id="thread-session-navigation" className="thread-session-navigation" aria-label="任务会话">
      <span className="eyebrow">WORKSPACE</span><h1>企业工作空间</h1>
      <button className="thread-session-new" disabled={creating} onClick={() => void newThread()}><Plus size={16} aria-hidden="true" />新建会话</button>
      <h2>工作中的会话</h2>
      {!sessions?.threads.some(item => item.threadId === createdThreadId) && <a aria-current="page" href={`/?workspace=enterprise&thread=${encodeURIComponent(createdThreadId)}`}>当前会话 · {createdThreadId.slice(-6)}</a>}
      {sessions?.threads.map(item => <a key={item.threadId} aria-current={item.threadId === createdThreadId ? 'page' : undefined}
        href={`/?workspace=enterprise&thread=${encodeURIComponent(item.threadId)}`}>{item.modelId || '工作会话'} · {item.threadId.slice(-6)}</a>)}
      {sessionError && <p role="status">会话列表暂不可用，当前对话仍可使用。</p>}
      {sessions?.hasMore && <button disabled={listingMore} onClick={() => {
        setListingMore(true)
        void transport!.listThreads(false, sessions.nextBeforeThreadId || undefined).then(page => setSessions(previous => ({...page,
          threads:[...new Map([...(previous?.threads || []), ...page.threads].map(item => [item.threadId,item])).values()]})))
          .catch(() => setSessionError(true)).finally(() => setListingMore(false))
      }}>{listingMore ? '加载中…' : '更多会话'}</button>}
    </nav>}
    prepareConnection={prepareConnection}
    disabledToolIds={disabledToolIds} onDisabledToolIdsChange={setDisabledToolIds}
    storageKey={`${namespace}.${createdThreadId}`} readOnly={archived} previewDiagram={previewDiagram}
    sessionNotice={error} headerActions={workspace ? undefined : <><a className="thread-new-dialogue" href={`/?workspace=enterprise&thread=${encodeURIComponent(createdThreadId)}`}>任务工作台</a><button type="button" className="thread-new-dialogue"
      disabled={creating} onClick={() => void newThread()} aria-label={creating ? '正在新建…' : '新建对话'}>
      <Plus size={16} aria-hidden="true" /><span>{creating ? '正在新建…' : '新建对话'}</span>
    </button></>} />
}
