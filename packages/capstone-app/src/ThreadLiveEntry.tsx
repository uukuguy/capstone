import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient } from './threadClient'
import { CapstoneClient } from './api'
import { HttpThreadTransport } from './threadHttpTransport'
import { parseNetworkDiagram } from './networkValidation'
import type { NetworkDiagram } from './types'
import ThreadSessionMenu from './ThreadSessionMenu'
import { rotateStorageNamespace, storageNamespace } from './threadSessionState'
import { readThreadAccess, type ThreadAccessMode } from './threadAccess'

const TOKEN_KEY = 'capstone.thread.operatorToken'

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

export default function ThreadLiveEntry({ threadId }: { threadId: string }) {
  const [token, setToken] = useState(readToken)
  const [accessMode, setAccessMode] = useState<ThreadAccessMode | null>(null)
  const [accessError, setAccessError] = useState<string | null>(null)
  const [accessRetry, setAccessRetry] = useState(0)
  const [createdThreadId, setCreatedThreadId] = useState(threadId === 'new' ? '' : threadId)
  const [creating, setCreating] = useState(threadId === 'new')
  const [error, setError] = useState<string | null>(null)
  const [previewDiagram, setPreviewDiagram] = useState<NetworkDiagram | null>(null)
  const [archived, setArchived] = useState(false)
  const newInFlight = useRef(false)
  const apiOrigin = import.meta.env.VITE_API_ORIGIN || ''
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
    const abort = new AbortController()
    const timeout = setTimeout(() => abort.abort(), 10000)
    let active = true
    setAccessError(null)
    void readThreadAccess(apiOrigin, abort.signal).then((mode) => {
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
      const snapshot = await client.create('ieee39', undefined, createdThreadId)
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

  if (accessError) return <main className="thread-token-shell"><div className="thread-token-card" role="alert"><h1>连接工作台</h1><p>{accessError}</p><button type="button" onClick={() => setAccessRetry((value) => value + 1)}>重试连接</button></div></main>
  if (accessMode === null) return <main className="thread-loading" aria-live="polite"><span className="spinner" />正在连接工作台…</main>
  if (accessMode === 'operator' && !token) return <TokenPrompt onSubmit={setToken} />
  if (error && !createdThreadId) return <main className="thread-token-shell"><div className="thread-token-card" role="alert"><h1>对话暂不可用</h1><p>{error}</p>{accessMode === 'open'
    ? <button type="button" onClick={() => void newThread()}>重试创建</button>
    : <button type="button" onClick={() => { setError(null); setToken('') }}>更换 token</button>}</div></main>
  if (!client || !createdThreadId) return <main className="thread-loading" aria-live="polite"><span className="spinner" />正在创建对话…</main>
  return <ThreadFixtureApp key={createdThreadId} client={client} threadId={createdThreadId}
    storageKey={`${namespace}.${createdThreadId}`} readOnly={archived} previewDiagram={previewDiagram}
    sessionNotice={error} headerActions={<ThreadSessionMenu transport={transport!}
      threadId={createdThreadId} creating={creating} onNew={() => void newThread()}
      onSelect={selectThread} onArchived={setArchived} />} />
}
