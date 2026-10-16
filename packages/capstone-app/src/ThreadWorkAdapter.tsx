import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MessageNotSentError } from '@assistant-ui/react'
import { Plus, RefreshCw } from 'lucide-react'
import ThreadWorkspace from './ThreadWorkspace'
import CapstoneAssistantThread, { projectAssistantActivity } from './CapstoneAssistantThread'
import { commandKey } from './commandKey'
import { buildWorkCommand, buildStartWorkCommand, buildCancelWorkCommand, parseStoredWorkCommand, parseWorkSnapshot, type WorkCommand } from './threadWorkProtocol'
import { HttpThreadTransport } from './threadHttpTransport'
import type { ThreadListPage } from './threadManagement'
import { CapstoneThreadClient } from './threadClient'
import { ThreadProjectionStore } from './threadProjectionStore'
import { canReconnect, readPendingCommands, reconnectDelay, writePendingCommands } from './threadSessionState'
import { projectWorkConversation } from './threadWorkMessages'

const statusCopy: Record<string, string> = { ready: '已保存，待执行', queued: '已排队', running: '执行中', completed: '已完成', failed: '执行失败', cancelled: '已取消', interrupted: '执行已中断', blocked: '执行不可用' }
const reasonCopy: Record<string, string> = { execution_unavailable: '当前任务的执行能力尚未接通，仍可保存目标和资料。', model_context_required: '当前任务没有专业模型，仍可保存资料。', capability_required: '当前任务尚未启用执行所需的业务能力，仍可保存目标和资料。', attempt_in_progress: '当前会话已有任务正在执行。', case_execution_active: '当前会话已有案例正在执行。', case_context_locked: '当前案例正在使用任务上下文，请等待其完成。', context_change_pending: '任务上下文正在更新，请稍后重试。', thread_archived: '此会话已归档。', run_not_open: '当前运行已关闭。' }

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
  const commandStorageKey = `${namespace}.${currentId}`
  const store = useMemo(() => new ThreadProjectionStore(new CapstoneThreadClient(transport), commandStorageKey, { protocolVersion: '2' }), [transport, commandStorageKey])
  const [projection, setProjection] = useState(store.state)
  const snapshot = projection.workSnapshot
  const professional = projection.snapshot
  const [reload, setReload] = useState(0)
  const [selected, setSelected] = useState('new')
  const [initialText, setInitialText] = useState('')
  const [restoredKey, setRestoredKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const pendingCommand = projection.pendingCommands.find(item => !item.receipt)?.command
  const pending = pendingCommand?.schema === 'capstone-command/2' ? pendingCommand : undefined
  const pendingMessage = pending?.kind === 'work_message' || pending?.kind === 'revise_goal' ? pending : undefined
  const drafts = useRef<Record<string, string>>({})
  const [sessions, setSessions] = useState<ThreadListPage | null>(null)
  const [sessionError, setSessionError] = useState(false)
  const [listingMore, setListingMore] = useState(false)
  const writing = useRef(false)
  const key = `${namespace}.${currentId}.work-draft`
  const persist = useCallback((target: string) => {
    if (!mounted.current) return
    try { sessionStorage.setItem(key, JSON.stringify({ selected: target, drafts: drafts.current })) }
    catch { /* Keep the current session draft in memory. */ }
  }, [key])
  const onDraftChange = useCallback((text: string) => {
    if (!mounted.current || store.state.pendingCommands.some(item => !item.receipt && ['work_message', 'revise_goal'].includes(item.command.kind))) return
    drafts.current[selected] = text
    persist(selected)
  }, [selected, persist, store])
  useEffect(() => {
    setError(null); setNotice('')
    const controller = new AbortController()
    let target = 'new'
    drafts.current = {}
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
      if (saved?.drafts && typeof saved.drafts === 'object') {
        drafts.current = Object.fromEntries(Object.entries(saved.drafts).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
      }
      if (typeof saved?.selected === 'string') target = saved.selected
      if (saved?.pending && !readPendingCommands(commandStorageKey, currentId).length) writePendingCommands(commandStorageKey, [parseStoredWorkCommand(saved.pending, currentId)])
      const command = readPendingCommands(commandStorageKey, currentId)[0]
      if (command?.schema === 'capstone-command/2') {
        target = command.target.id
        if (command.kind === 'work_message' || command.kind === 'revise_goal') drafts.current[target] = String(command.payload.text)
      }
    } catch { /* Invalid local state cannot create or submit a command. */ }
    setSelected(target); setInitialText(drafts.current[target] || ''); setRestoredKey(key)
    return () => controller.abort()
  }, [key, currentId, commandStorageKey])
  useEffect(() => {
    const controller = new AbortController()
    void transport.listThreads(false, undefined, controller.signal).then(page => {
      if (!controller.signal.aborted) { setSessions(page); setSessionError(false) }
    }).catch(() => { if (!controller.signal.aborted) setSessionError(true) })
    return () => controller.abort()
  }, [transport, currentId])
  useEffect(() => {
    if (currentId === 'new') return
    let live = true
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    const unsubscribe = store.subscribe(() => { if (live) setProjection({ ...store.state }) })
    async function connect() {
      try {
        await store.load(currentId)
        if (!live) return
        await store.catchUp()
        if (!live) return
        setError(null)
        if (store.canStreamEvents) await store.consumeEvents(controller.signal)
      } catch (cause) {
        if (!live || controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : '实时连接暂不可用。')
        if (canReconnect(cause)) timer = setTimeout(() => { if (live) void connect() }, reconnectDelay(failures++))
      }
    }
    void connect()
    return () => { live = false; controller.abort(); if (timer) clearTimeout(timer); unsubscribe(); store.dispose() }
  }, [store, currentId, reload])
  function selectWork(target: string) {
    if (pending || writing.current) return
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
  const selectedWork = snapshot?.works.find(work => work.workId === selected)
  const active = selectedWork?.status === 'queued' || selectedWork?.status === 'running'
  const canStop = active && selectedWork.latestAttemptId === professional?.currentAttempt?.attemptId
  async function dispatch(command: WorkCommand) {
    if (recoveryOnly && !(pending && JSON.stringify(command) === JSON.stringify(pending)) && !(command.kind === 'cancel_work' && canStop && !pending)) throw new Error('此入口只可确认原请求或停止已有执行。')
    if (writing.current) throw new Error('请等待当前操作完成。')
    writing.current = true; setBusy(true); setError(null); setNotice('')
    try {
      const receipt = await store.dispatch(command)
      if (!mounted.current) return
      if (receipt.status === 'rejected') throw new Error(receipt.rejection === 'revision_conflict' ? '任务已更新，请核对最新内容后再次提交。' : `未保存：${receipt.rejection || '请求被拒绝'}`)
      if (receipt.status !== 'accepted') throw new Error('操作结果待确认，请重试原请求。')
      if (command.kind === 'work_message' || command.kind === 'revise_goal') { drafts.current[selected] = ''; persist(selected) }
      setNotice(command.kind === 'start_work' ? '执行请求已接收；排队、执行与结果以实际任务状态为准。' : command.kind === 'cancel_work' ? active ? '停止请求已接收，正在等待实际执行停止。' : '停止请求已确认。' : '任务已保存。保存资料不会自动启动分析。')
      await store.refreshWorkSnapshot().catch(cause => { if (mounted.current) setError(cause.message) })
      if (!mounted.current) return
      if (selected === 'new' && typeof receipt.target?.id === 'string' && receipt.target.id !== 'new') {
        const id = receipt.target.id; setSelected(id); setInitialText(drafts.current[id] || ''); persist(id)
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : '操作结果待确认，请重试原请求。')
      if (mounted.current && canReconnect(cause)) setReload(value => value + 1)
      throw cause
    } finally { writing.current = false; if (mounted.current) setBusy(false) }
  }
  async function send(text: string) {
    const runId = snapshot?.runId ?? professional?.run.runId
    if (!runId) throw new MessageNotSentError('请先连接会话。')
    try {
      await dispatch(pendingMessage || buildWorkCommand(currentId, runId, `cmd_${commandKey()}`, `idem_${commandKey()}`, selected, selectedWork?.revision || 0, text))
    } catch (cause) { throw new MessageNotSentError(cause instanceof Error ? cause.message : '保存结果待确认。') }
  }
  async function start() {
    if (!selectedWork || !snapshot || (recoveryOnly && pending?.kind !== 'start_work')) return
    try {
      await dispatch(pending?.kind === 'start_work' ? pending : buildStartWorkCommand(currentId, snapshot.runId, `cmd_${commandKey()}`, `idem_${commandKey()}`, selectedWork.workId, selectedWork.revision))
    } catch { /* The shared store retains uncertain requests for explicit retry. */ }
  }
  async function cancel() {
    if (!selectedWork || !snapshot || (pending?.kind !== 'cancel_work' && !canStop)) return
    try {
      await dispatch(pending?.kind === 'cancel_work' ? pending : buildCancelWorkCommand(currentId, snapshot.runId, `cmd_${commandKey()}`, `idem_${commandKey()}`, selectedWork.workId, selectedWork.revision))
    } catch { /* The original cancel request remains recoverable through the shared command store. */ }
  }
  async function recoverLegacyCommand() {
    if (!pendingCommand || pendingCommand.schema !== 'capstone-command/1' || writing.current) return
    writing.current = true; setBusy(true)
    try {
      const receipt = await store.dispatch(pendingCommand)
      if (!mounted.current) return
      setNotice(receipt.status === 'rejected' ? '原对话请求未获接收，请核对历史记录。' : '原对话请求已确认。')
      await store.refreshWorkSnapshot()
    } catch (cause) {
      if (mounted.current) { setError(cause instanceof Error ? cause.message : '原请求结果待确认。'); if (canReconnect(cause)) setReload(value => value + 1) }
    } finally { writing.current = false; if (mounted.current) setBusy(false) }
  }
  const conversation = projectWorkConversation(store.publicEvents, selectedWork, snapshot?.works, !snapshot)
  const startReason = selectedWork?.startUnavailableReason || selectedWork?.blockedReason
  return <ThreadWorkspace conversationOnly subtitle="企业任务工作台"
    sidebar={<nav id="thread-session-navigation" className="thread-session-navigation" aria-label="任务与会话">
      {recoveryOnly ? <a className="thread-session-new" href="/?workspace=enterprise&thread=new">新建会话</a> : <button className="thread-session-new" disabled={busy} onClick={() => void create()}><Plus aria-hidden="true" size={16} />新建任务会话</button>}
      <h2>当前会话</h2>
      {!recoveryOnly && <button aria-pressed={selected === 'new'} disabled={busy || !!pending} onClick={() => selectWork('new')}>新的任务目标</button>}
      {snapshot?.works.map((work, index) => <button key={work.workId} aria-pressed={selected === work.workId}
        disabled={busy || !!pending} onClick={() => selectWork(work.workId)} title={work.goal}>{String(index + 1).padStart(2, '0')} · {work.goal}</button>)}
      <h2>最近会话</h2>
      {sessionError && <p role="status">会话列表暂不可用，当前任务仍可使用。</p>}
      {sessions?.threads.map(item => <a key={item.threadId} aria-current={item.threadId === currentId ? 'page' : undefined}
        href={`/?workspace=enterprise&thread=${encodeURIComponent(item.threadId)}`}>
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
      <span className="thread-model-short">{selectedWork ? `修订 ${selectedWork.goalRevision} · ${selectedWork.cancelRequested ? '停止请求中' : statusCopy[selectedWork.status] || selectedWork.status}` : '对话与任务记录'}</span></div>
      <div className="thread-chat-heading-meta">
        {pending?.kind === 'cancel_work' && !canStop && <button type="button" className="thread-control-button" disabled={busy || projection.connection !== 'live'} onClick={() => void cancel()}>重试停止请求</button>}
        {pendingCommand?.schema === 'capstone-command/1' && <button type="button" className="thread-control-button" disabled={busy || projection.connection !== 'live'} onClick={() => void recoverLegacyCommand()}>重试原对话请求</button>}
        {selectedWork && (!recoveryOnly || pending?.kind === 'start_work') && <button type="button" className="thread-primary-button" disabled={busy || (!!pending && pending.kind !== 'start_work') || (!selectedWork.startAvailable && pending?.kind !== 'start_work') || projection.connection !== 'live'}
          aria-describedby={!selectedWork.startAvailable ? 'work-start-reason' : undefined} onClick={() => void start()}>{pending?.kind === 'start_work' ? '重试执行请求' : '开始任务'}</button>}
        {currentId !== 'new' && <button type="button" className="thread-control-button" aria-label="刷新任务" onClick={() => setReload(value => value + 1)}><RefreshCw aria-hidden="true" size={16} /></button>}
      </div>
    </div>
      {recoveryOnly && <p role="status">此会话使用旧版任务协议，可查看历史、保留草稿、确认原请求及停止已有执行；当前入口尚不能继续发送。可新建会话继续工作。</p>}
      {error && <p role="alert">{error}</p>}
      {selectedWork && !selectedWork.startAvailable && <p id="work-start-reason" role="status">{startReason ? reasonCopy[startReason] || '当前任务暂不可启动，请刷新后查看最新状态。仍可保存目标和资料。' : '当前任务暂不可启动，仍可保存资料。'}</p>}
      {notice && <p role="status">{notice}</p>}
      {conversation.hasUnattributedHistory && <p role="status">部分历史执行记录尚未确认任务归属。可加载更早的记录后查看。</p>}
    </>}
  >
    {restoredKey === key && (snapshot || professional || currentId === 'new') && <CapstoneAssistantThread key={`${key}.${selected}`} events={conversation.events}
      projectedMessages={conversation.messages} composerMode="text" composerLabel={selected === 'new' ? '任务目标' : '补充任务资料'}
      sendLabel={pendingMessage ? '重试保存' : '保存任务'} initialText={initialText} onDraftChange={onDraftChange}
      storageKey={`${key}.${selected}`} disabled={(recoveryOnly && !pendingMessage) || busy || (!snapshot && !professional) || !!professional?.currentAttempt || active || (!!pendingCommand && !pendingMessage) || projection.connection !== 'live'} lockDraft={!!pendingMessage}
      isRunning={active} canCancel={canStop}
      cancelLabel={pending?.kind === 'cancel_work' ? '重试停止请求' : selectedWork?.cancelRequested ? '停止请求中' : '停止任务'}
      cancelDisabled={busy || projection.connection !== 'live' || (!!pending && pending.kind !== 'cancel_work') || (selectedWork?.cancelRequested === true && pending?.kind !== 'cancel_work')}
      activity={projectAssistantActivity(conversation.events)}
      runtimeStatus={<span>{pending ? '上次操作结果待确认；重试将使用同一请求。' : projection.connection !== 'live' && currentId !== 'new' ? '连接已断开，后台状态待确认。' : '目标与资料保存在当前任务中。保存不会自动启动执行。'}</span>}
      emptyState={<div className="capstone-chat-empty"><strong>有什么工作需要完成？</strong><p>{currentId === 'new' ? '新建任务会话后，描述目标、已有资料与期望交付。' : '描述目标、已有资料与期望交付。'}</p></div>}
      onSend={(_, text) => send(text)} onCancel={cancel} canRerunCompleted={false}
      hasOlderHistory={projection.hasOlderHistory} historyLoading={projection.historyLoading} onLoadOlder={() => store.loadOlderHistory()}
      resultProjections={professional?.resultProjections}
      caseExecution={professional?.applicationState?.caseExecution}
      onReadAttemptRecords={professional ? (attemptId, after) => transport.readAttemptRecords(currentId, attemptId, after) : undefined} />}
  </ThreadWorkspace>
}
