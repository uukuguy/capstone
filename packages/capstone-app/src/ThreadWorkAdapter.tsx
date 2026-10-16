import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageNotSentError, type ThreadMessageLike } from '@assistant-ui/react'
import { Plus, RefreshCw } from 'lucide-react'
import ThreadWorkspace from './ThreadWorkspace'
import CapstoneAssistantThread, { projectAssistantMessages } from './CapstoneAssistantThread'
import { commandKey } from './commandKey'
import { parseCommandReceipt } from './threadProtocol'
import { buildWorkCommand, parseWorkSnapshot, type WorkCommand, type WorkSnapshot } from './threadWorkProtocol'
import { HttpThreadTransport, ThreadTransportError } from './threadHttpTransport'
import type { ThreadListPage } from './threadManagement'
import { parseThreadHistoryPage, type ThreadHistoryPage } from './threadHistory'

/** Data adapter for the existing workspace and assistant-ui presentation. */
export default function ThreadWorkAdapter({ transport, threadId, namespace, recoveryOnly = false }: {
  transport: HttpThreadTransport; threadId: string; namespace: string; recoveryOnly?: boolean
}) {
  const [currentId, setCurrentId] = useState(threadId)
  useEffect(() => {
    const navigate = () => { const id = new URLSearchParams(window.location.search).get('thread'); if (id) setCurrentId(id) }
    window.addEventListener('popstate', navigate)
    return () => window.removeEventListener('popstate', navigate)
  }, [])
  return <WorkThreadSession key={currentId} transport={transport} threadId={currentId} namespace={namespace} onNavigate={setCurrentId} recoveryOnly={recoveryOnly} />
}

function WorkThreadSession({ transport, threadId: currentId, namespace, onNavigate, recoveryOnly }: {
  transport: HttpThreadTransport; threadId: string; namespace: string; onNavigate: (id: string) => void; recoveryOnly: boolean
}) {
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [snapshot, setSnapshot] = useState<WorkSnapshot | null>(null)
  const [selected, setSelected] = useState('new')
  const [initialText, setInitialText] = useState('')
  const [restoredKey, setRestoredKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState<WorkCommand | null>(null)
  const pendingRef = useRef<WorkCommand | null>(null)
  const drafts = useRef<Record<string, string>>({})
  const [sessions, setSessions] = useState<ThreadListPage | null>(null)
  const [sessionError, setSessionError] = useState(false)
  const [listingMore, setListingMore] = useState(false)
  const [history, setHistory] = useState<ThreadHistoryPage | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyReload, setHistoryReload] = useState(0)
  const writing = useRef(false)
  const key = `${namespace}.${currentId}.work-draft`
  const updatePending = (command: WorkCommand | null) => { pendingRef.current = command; setPending(command) }
  const persist = useCallback((target: string) => {
    if (!mounted.current) return
    try { sessionStorage.setItem(key, JSON.stringify({ selected: target, drafts: drafts.current, pending: pendingRef.current })) }
    catch { /* Keep the current session draft in memory. */ }
  }, [key])
  const onDraftChange = useCallback((text: string) => {
    if (!mounted.current || pendingRef.current) return
    drafts.current[selected] = text
    persist(selected)
  }, [selected, persist])
  const load = useCallback(async (signal?: AbortSignal) => {
    if (currentId === 'new') return
    const raw = await transport.getSnapshot(currentId, signal)
    if (raw && typeof raw === 'object' && 'schema' in raw && raw.schema === 'capstone-thread-snapshot/1') {
      if (mounted.current && !signal?.aborted) window.location.replace(`/?thread=${encodeURIComponent(currentId)}`)
      return
    }
    const next = parseWorkSnapshot(raw)
    if (next.threadId !== currentId) throw new Error('会话身份不一致')
    if (mounted.current && !signal?.aborted) setSnapshot(next)
  }, [transport, currentId])
  useEffect(() => {
    setSnapshot(null); setHistory(null); setError(null); setNotice('')
    const controller = new AbortController()
    let target = 'new'
    drafts.current = {}; updatePending(null)
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
      if (saved?.drafts && typeof saved.drafts === 'object') {
        drafts.current = Object.fromEntries(Object.entries(saved.drafts).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
      }
      if (typeof saved?.selected === 'string') target = saved.selected
      const command = saved?.pending
      if (command?.schema === 'capstone-command/2' && command.thread_id === currentId) {
        const restored = buildWorkCommand(command.thread_id, command.run_id, command.command_id,
          command.idempotency_key, command.target.id, command.target.expected_revision, command.payload.text, command.kind)
        updatePending(restored); target = restored.target.id; drafts.current[target] = restored.payload.text
      }
    } catch { /* Invalid local state cannot create or submit a command. */ }
    setSelected(target); setInitialText(drafts.current[target] || ''); setRestoredKey(key)
    void load(controller.signal).catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
    return () => controller.abort()
  }, [key, currentId, load])
  useEffect(() => {
    const controller = new AbortController()
    void transport.listThreads(false, undefined, controller.signal).then(page => {
      if (!controller.signal.aborted) { setSessions(page); setSessionError(false) }
    }).catch(() => { if (!controller.signal.aborted) setSessionError(true) })
    return () => controller.abort()
  }, [transport, currentId])
  const hasProfessionalHistory = Boolean(snapshot?.professionalSnapshot)
  useEffect(() => {
    if (!hasProfessionalHistory) return
    const controller = new AbortController()
    setHistoryLoading(true); setHistoryError(null)
    void transport.readHistory(currentId, undefined, controller.signal).then(raw => {
      if (!controller.signal.aborted) setHistory(parseThreadHistoryPage(raw, currentId))
    }).catch(cause => { if (!controller.signal.aborted) setHistoryError(cause.message) })
      .finally(() => { if (!controller.signal.aborted) setHistoryLoading(false) })
    return () => controller.abort()
  }, [transport, currentId, hasProfessionalHistory, historyReload])
  async function older() {
    if (!history || historyLoading) return
    setHistoryLoading(true)
    try {
      const page = parseThreadHistoryPage(await transport.readHistory(currentId, history.nextBeforeEventSeq), currentId, history.nextBeforeEventSeq)
      if (!mounted.current) return
      setHistory({ ...page, events: [...page.events, ...history.events] })
    } finally { if (mounted.current) setHistoryLoading(false) }
  }
  function selectWork(target: string) {
    if (pendingRef.current || writing.current) return
    persist(target); setSelected(target); setInitialText(drafts.current[target] || '')
  }
  async function create() {
    if (writing.current) return
    writing.current = true; setBusy(true); setError(null)
    try {
      const next = parseWorkSnapshot(await transport.createWorkThread())
      if (!mounted.current) return
      const url = new URL(window.location.href)
      url.searchParams.set('workspace', 'enterprise'); url.searchParams.set('thread', next.threadId)
      window.history.pushState({}, '', url); onNavigate(next.threadId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '创建失败，请重试。') }
    finally { writing.current = false; setBusy(false) }
  }
  async function send(text: string) {
    if (!snapshot || writing.current) throw new MessageNotSentError('请先连接会话。')
    writing.current = true; setBusy(true); setError(null); setNotice('')
    try {
      const target = snapshot.works.find(work => work.workId === selected)
      const command = pendingRef.current || buildWorkCommand(snapshot.threadId, snapshot.runId,
        `cmd_${commandKey()}`, `idem_${commandKey()}`, selected, target?.revision || 0, text)
      drafts.current[selected] = command.payload.text
      updatePending(command); persist(selected)
      const rawReceipt = await transport.sendCommand(command)
      // The old Thread retains its pending command for exact-key recovery.
      if (!mounted.current) return
      const receipt = parseCommandReceipt(rawReceipt)
      if (receipt.commandId !== command.command_id || receipt.threadId !== currentId || receipt.idempotencyKey !== command.idempotency_key) throw new Error('任务回执身份不一致')
      if (receipt.status === 'rejected') {
        updatePending(null); persist(selected)
        void load().catch(() => {})
        throw new Error(receipt.rejection === 'revision_conflict' ? '任务已更新，请核对最新内容后再次提交。' : `未保存：${receipt.rejection || '请求被拒绝'}`)
      }
      if (receipt.status !== 'accepted') throw new Error('保存结果待确认，请重试原请求。')
      updatePending(null); drafts.current[selected] = ''; persist(selected)
      setNotice('任务已保存。持续执行尚未接通，本次未启动分析。')
      // A read failure after acknowledgement must not turn a saved command into a new submission.
      await load().catch(cause => setError(cause.message))
      if (!mounted.current) return
      if (selected === 'new' && typeof receipt.target?.id === 'string' && receipt.target.id !== 'new') {
        const workId = receipt.target.id
        setSelected(workId); setInitialText(drafts.current[workId] || ''); persist(workId)
      }
    } catch (cause) {
      if (!mounted.current) throw new MessageNotSentError('原会话保存结果待确认。')
      if (cause instanceof ThreadTransportError && [400, 401, 403, 422].includes(cause.status)) {
        updatePending(null); persist(selected)
      }
      const message = cause instanceof Error ? cause.message : '未能确认保存结果，请重试原请求。'
      setError(message)
      throw new MessageNotSentError(message)
    } finally { writing.current = false; setBusy(false) }
  }
  const messages = useMemo<ThreadMessageLike[]>(() => [
    ...projectAssistantMessages(history?.events || []),
    ...(snapshot?.works || []).filter(work => work.workId === selected).flatMap(work =>
      work.messages.map((text, index) => ({ id: `${work.workId}-message-${index}`, role: 'user' as const, content: text,
        metadata: { custom: { workId: work.workId } } }))),
  ], [history, snapshot, selected])
  const selectedWork = snapshot?.works.find(work => work.workId === selected)
  return <ThreadWorkspace conversationOnly subtitle="企业任务工作台"
    sidebar={<nav id="thread-session-navigation" className="thread-session-navigation" aria-label="任务与会话">
      <span className="eyebrow">WORKSPACE</span><h1>企业工作空间</h1>
      {recoveryOnly ? <a className="thread-session-new" href="/?workspace=enterprise&thread=new">新建会话</a> : <button className="thread-session-new" disabled={busy} onClick={() => void create()}><Plus aria-hidden="true" size={16} />新建任务会话</button>}
      <h2>当前会话</h2>
      {!recoveryOnly && <button aria-pressed={selected === 'new'} disabled={busy || !!pending} onClick={() => selectWork('new')}>新的任务目标</button>}
      {snapshot?.works.map((work, index) => <button key={work.workId} aria-pressed={selected === work.workId}
        disabled={busy || !!pending} onClick={() => selectWork(work.workId)} title={work.goal}>{String(index + 1).padStart(2, '0')} · {work.goal}</button>)}
      <h2>最近会话</h2>
      {sessionError && <p role="status">会话列表暂不可用，当前任务仍可使用。</p>}
      {sessions?.threads.map(item => <a key={item.threadId} aria-current={item.threadId === currentId ? 'page' : undefined}
        href={`/?${item.minimumProtocolVersion === 2 ? 'workspace=enterprise&' : ''}thread=${encodeURIComponent(item.threadId)}`}>
        {item.modelId || '企业任务'} · {item.threadId.slice(-6)}</a>)}
      {sessions?.hasMore && <button disabled={listingMore} onClick={() => {
        setListingMore(true)
        void transport.listThreads(false, sessions.nextBeforeThreadId || undefined).then(page => setSessions(before => ({ ...page,
          threads: [...new Map([...(before?.threads || []), ...page.threads].map(item => [item.threadId, item])).values()] })))
          .catch(() => setSessionError(true)).finally(() => setListingMore(false))
      }}>{listingMore ? '加载中…' : '更多会话'}</button>}
      <a href="/?thread=new">智能体对话</a>
    </nav>}
    heading={<><div className="thread-chat-heading"><div className="thread-chat-heading-title"><h2>{selectedWork?.goal || '新的工作'}</h2>
      <span className="thread-model-short">{selectedWork ? `修订 ${selectedWork.goalRevision} · 已保存，未执行` : '对话与任务记录'}</span></div>
      {currentId !== 'new' && <button type="button" className="thread-control-button" aria-label="刷新任务" onClick={() => { setError(null); void load().catch(cause => setError(cause.message)) }}><RefreshCw aria-hidden="true" size={16} /></button>}
    </div>
      {recoveryOnly && <p role="status">此会话使用旧版任务协议，可查看历史、保留草稿并确认原请求；当前入口尚不能继续发送。可新建会话继续工作。</p>}
      {error && <p role="alert">{error}</p>}
      {historyError && <p role="alert">{historyError} <button onClick={() => setHistoryReload(value => value + 1)}>重试读取历史</button></p>}
      {notice && <p role="status">{notice}</p>}
    </>}
  >
    {restoredKey === key && (snapshot || currentId === 'new') && <CapstoneAssistantThread key={`${key}.${selected}`} events={history?.events || []}
      projectedMessages={messages} composerMode="text" composerLabel={selected === 'new' ? '任务目标' : '补充任务资料'}
      sendLabel={pending ? '重试保存' : '保存任务'} initialText={initialText} onDraftChange={onDraftChange}
      storageKey={`${key}.${selected}`} disabled={busy || !snapshot || (recoveryOnly && !pending)} lockDraft={!!pending} isRunning={false} activity={[]}
      runtimeStatus={<span>{pending ? '上次保存结果待确认；重试将使用同一请求。' : '任务记录已开放。持续执行尚未接通，保存任务不会启动智能体。'}</span>}
      emptyState={<div className="capstone-chat-empty"><strong>有什么工作需要完成？</strong><p>{currentId === 'new' ? '新建任务会话后，描述目标、已有资料与期望交付。' : '描述目标、已有资料与期望交付。'}</p></div>}
      onSend={(_, text) => send(text)} onCancel={async () => {}} canRerunCompleted={false}
      hasOlderHistory={history?.hasMore} historyLoading={historyLoading} onLoadOlder={older}
      resultProjections={snapshot?.professionalSnapshot?.resultProjections}
      caseExecution={snapshot?.professionalSnapshot?.applicationState?.caseExecution}
      onReadAttemptRecords={hasProfessionalHistory ? (attemptId, after) => transport.readAttemptRecords(currentId, attemptId, after) : undefined} />}
  </ThreadWorkspace>
}
