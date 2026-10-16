import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowUp, FileText, Plus, RefreshCw } from 'lucide-react'
import { PageHeader } from './AppHeader'
import { commandKey } from './commandKey'
import { parseCommandReceipt } from './threadProtocol'
import { buildWorkCommand, parseWorkSnapshot, type WorkCommand, type WorkSnapshot } from './threadWorkProtocol'
import { HttpThreadTransport, ThreadTransportError } from './threadHttpTransport'
import type { ThreadListPage } from './threadManagement'
import { parseThreadHistoryPage, type ThreadHistoryPage } from './threadHistory'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import type { ThreadSnapshot } from './threadProtocol'
import './threadWork.css'

function ProfessionalHistory({ transport, snapshot }: { transport: HttpThreadTransport; snapshot: ThreadSnapshot }) {
  const [history, setHistory] = useState<ThreadHistoryPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(null); setLoading(true)
    void transport.readHistory(snapshot.threadId, undefined, controller.signal).then(raw => {
      if (!controller.signal.aborted) setHistory(parseThreadHistoryPage(raw, snapshot.threadId))
    }).catch(cause => { if (!controller.signal.aborted) setError(cause.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [transport, snapshot.threadId, reload])
  async function older() {
    if (!history || loading) return
    setLoading(true); setError(null)
    try {
      const page = parseThreadHistoryPage(await transport.readHistory(snapshot.threadId, history.nextBeforeEventSeq), snapshot.threadId, history.nextBeforeEventSeq)
      setHistory({ ...page, events: [...page.events, ...history.events] })
    } catch (cause) { setError(cause instanceof Error ? cause.message : '历史读取失败') }
    finally { setLoading(false) }
  }
  return <details className="work-professional-history" open><summary>已有专业对话与结果 · 只读</summary>
    {error && <p role="alert">{error} <button onClick={() => setReload(value => value + 1)}>重试读取历史</button></p>}
    {loading && !history && <p role="status">正在恢复已有记录…</p>}
    {history && <CapstoneAssistantThread events={history.events} readOnly disabled isRunning={false}
      activity={[]} onSend={async () => {}} onCancel={async () => {}} canRerunCompleted={false}
      hasOlderHistory={history.hasMore} historyLoading={loading} onLoadOlder={older}
      resultProjections={snapshot.resultProjections} caseExecution={snapshot.applicationState?.caseExecution}
      onReadAttemptRecords={(attemptId, after) => transport.readAttemptRecords(snapshot.threadId, attemptId, after)}
      storageKey={`${snapshot.threadId}.professional-history`} />}
  </details>
}

/** A view of the existing Thread ledger. It does not run or simulate a task. */
export default function ThreadWorkView({ transport, threadId, namespace }: {
  transport: HttpThreadTransport; threadId: string; namespace: string
}) {
  const [currentId, setCurrentId] = useState(threadId)
  const [snapshot, setSnapshot] = useState<WorkSnapshot | null>(null)
  const [text, setText] = useState('')
  const [selected, setSelected] = useState('new')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState<WorkCommand | null>(null)
  const [sessions, setSessions] = useState<ThreadListPage | null>(null)
  const [sessionError, setSessionError] = useState(false)
  const [listingMore, setListingMore] = useState(false)
  const writing = useRef(false)
  const key = `${namespace}.${currentId}.work-draft`
  const load = useCallback(async (signal?: AbortSignal) => {
    if (currentId === 'new') return
    const raw = await transport.getSnapshot(currentId, signal)
    if (raw && typeof raw === 'object' && 'schema' in raw && raw.schema === 'capstone-thread-snapshot/1') {
      if (!signal?.aborted) window.location.replace(`/?thread=${encodeURIComponent(currentId)}`)
      return
    }
    const next = parseWorkSnapshot(raw)
    if (next.threadId !== currentId) throw new Error('会话身份不一致')
    if (!signal?.aborted) setSnapshot(next)
  }, [transport, currentId])
  useEffect(() => {
    setSnapshot(null); setSelected('new'); setError(null); setNotice('')
    const abort = new AbortController()
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
      const restoredTarget = typeof saved?.selected === 'string' ? saved.selected : 'new'
      setSelected(restoredTarget)
      setText(typeof saved?.drafts?.[restoredTarget] === 'string' ? saved.drafts[restoredTarget] : '')
      const command = saved?.pending
      if (command?.schema === 'capstone-command/2' && command.thread_id === currentId) {
        setPending(buildWorkCommand(command.thread_id, command.run_id, command.command_id,
          command.idempotency_key, command.target.id, command.target.expected_revision, command.payload.text, command.kind))
        setSelected(command.target.id); setText(command.payload.text)
      } else setPending(null)
    } catch { setText(''); setPending(null) }
    void load(abort.signal).catch(cause => { if (!abort.signal.aborted) setError(String(cause.message || cause)) })
    return () => abort.abort()
  }, [key, currentId, load])
  useEffect(() => {
    const controller = new AbortController()
    void transport.listThreads(false, undefined, controller.signal).then(page => {
      if (!controller.signal.aborted) { setSessions(page); setSessionError(false) }
    }).catch(() => { if (!controller.signal.aborted) setSessionError(true) })
    return () => controller.abort()
  }, [transport, currentId])
  const saveDraft = (value: string, command: WorkCommand | null) => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
      sessionStorage.setItem(key, JSON.stringify({ selected, drafts: { ...saved?.drafts, [selected]: value }, pending: command }))
    } catch { /* Current view retains draft. */ }
  }
  function selectWork(target: string) {
    saveDraft(text, pending)
    let draft = ''
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
      draft = typeof saved?.drafts?.[target] === 'string' ? saved.drafts[target] : ''
      sessionStorage.setItem(key, JSON.stringify({ ...saved, selected: target }))
    } catch { /* The selected Work remains explicit in this view. */ }
    setSelected(target); setText(draft)
  }
  async function create() {
    if (writing.current) return
    writing.current = true; setBusy(true); setError(null)
    try {
      const next = parseWorkSnapshot(await transport.createWorkThread())
      const url = new URL(window.location.href)
      url.searchParams.set('workspace', 'enterprise'); url.searchParams.set('thread', next.threadId)
      window.history.replaceState({}, '', url)
      setCurrentId(next.threadId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '创建失败，请重试。') }
    finally { writing.current = false; setBusy(false) }
  }
  async function send() {
    if (!snapshot || writing.current) return
    writing.current = true; setBusy(true); setError(null); setNotice('')
    try {
      const target = snapshot.works.find(work => work.workId === selected)
      const command = pending || buildWorkCommand(snapshot.threadId, snapshot.runId, `cmd_${commandKey()}`, `idem_${commandKey()}`,
        selected, target?.revision || 0, text)
      setPending(command); saveDraft(text, command)
      const receipt = parseCommandReceipt(await transport.sendCommand(command))
      if (receipt.commandId !== command.command_id || receipt.threadId !== currentId) throw new Error('任务回执身份不一致')
      if (receipt.status === 'rejected') {
        setPending(null); saveDraft(text, null)
        await load()
        setError(receipt.rejection === 'revision_conflict' ? '任务已更新，请核对最新内容后再次提交。' : `未保存：${receipt.rejection || '请求被拒绝'}`)
        return
      }
      setPending(null); setText(''); saveDraft('', null)
      await load()
      setNotice('任务已保存。持续执行尚未接通，本次未启动分析。')
    } catch (cause) {
      if (cause instanceof ThreadTransportError && [400, 401, 403, 422].includes(cause.status)) {
        setPending(null); saveDraft(text, null)
      }
      setError(cause instanceof Error ? cause.message : '未能确认保存结果，请重试原请求。')
    }
    finally { writing.current = false; setBusy(false) }
  }
  return <div className="thread-app-shell work-shell">
    <PageHeader showThreadEntry={false} subtitle="企业任务工作台" actions={<a className="thread-entry-link" href="/?thread=new">智能体对话</a>} />
    <main className="work-main">
      <aside className="work-rail" aria-label="任务导航">
        <span className="eyebrow">WORKSPACE</span><h1>任务工作台</h1>
        <p>目标、上下文与成果，保存在同一会话中。</p>
        <button className="work-new" onClick={() => void create()} disabled={busy}><Plus size={16} />新建任务会话</button>
        <div className="work-section-label">当前会话</div>
        <button className={`work-item ${selected === 'new' ? 'is-active' : ''}`} aria-pressed={selected === 'new'} disabled={!!pending} onClick={() => selectWork('new')}><Plus size={16} />新的任务目标</button>
        {snapshot?.works.map((work, index) => <button key={work.workId} className={`work-item ${selected === work.workId ? 'is-active' : ''}`}
          aria-pressed={selected === work.workId} disabled={!!pending} onClick={() => selectWork(work.workId)}><FileText size={16} /><span>{String(index + 1).padStart(2, '0')} · {work.goal}</span></button>)}
        <div className="work-section-label">最近会话</div>
        {sessionError && <span className="work-list-note">会话列表暂不可用，当前任务仍可使用。</span>}
        {sessions?.threads.map(item => <a key={item.threadId} className={`work-item ${item.threadId === currentId ? 'is-active' : ''}`}
          aria-current={item.threadId === currentId ? 'page' : undefined} href={`/?${item.minimumProtocolVersion === 2 ? 'workspace=enterprise&' : ''}thread=${encodeURIComponent(item.threadId)}`}>
          <FileText size={16} /><span>{item.modelId || '企业任务'} · {item.threadId.slice(-6)}</span></a>)}
        {sessions?.hasMore && <button className="work-item" disabled={listingMore} onClick={() => {
          setListingMore(true)
          void transport.listThreads(false, sessions.nextBeforeThreadId || undefined).then(page => setSessions(before => ({ ...page,
            threads: [...new Map([...(before?.threads || []), ...page.threads].map(item => [item.threadId, item])).values()] })))
            .catch(() => setSessionError(true)).finally(() => setListingMore(false))
        }}>{listingMore ? '加载中…' : '更多会话'}</button>}
        <div className="work-rail-foot">共同基座 · 研发预览</div>
      </aside>
      <section className="work-conversation" aria-label="任务内容">
        <header className="work-heading"><div><span className="eyebrow">CAPSTONE / WORK</span><h2>从一个清晰的目标开始</h2></div>
          {currentId !== 'new' && <button aria-label="刷新任务" onClick={() => { setError(null); void load().catch(cause => setError(cause.message)) }}><RefreshCw size={16} /></button>}</header>
        <div className="work-notice">任务记录与恢复已开放。持续执行尚未接通，保存任务不会启动智能体。</div>
        {error && <p className="work-error" role="alert">{error}</p>}
        {notice && <p className="work-saved" role="status">{notice}</p>}
        <div className="work-records">
          {snapshot?.professionalSnapshot && <ProfessionalHistory transport={transport} snapshot={snapshot.professionalSnapshot} />}
          {!snapshot?.works.length && <div className="work-empty"><FileText size={32} /><h3>让目标成为可持续的工作</h3><p>描述需要完成的工作，稍后可回到同一任务补充资料。</p></div>}
          {snapshot?.works.filter(work => selected === 'new' || work.workId === selected).map(work => <article className="work-record" key={work.workId}>
            <div className="work-record-meta"><span>任务目标</span><span>修订 {work.goalRevision} · 已保存，未执行</span></div>
            <h3>{work.goal}</h3>{work.messages.filter((message, index) => index > 0 || message !== work.goal).map((message, index) => <p key={index}>{message}</p>)}
          </article>)}
        </div>
        {snapshot && <form className="work-composer" onSubmit={event => { event.preventDefault(); void send() }}>
          <label htmlFor="work-goal">{selected === 'new' ? '任务目标' : '补充任务资料'}</label>
          <textarea id="work-goal" value={text} maxLength={65536} disabled={busy || !!pending}
            placeholder="描述目标、已有资料与期望交付…" onChange={event => { setText(event.target.value); saveDraft(event.target.value, null) }} />
          <div><span>{pending ? '上次保存结果待确认；重试将使用同一请求。' : '内容将保存到当前会话。'}</span>
            <button type="submit" disabled={busy || (!pending && !text.trim())}><ArrowUp size={16} />{busy ? '保存中…' : pending ? '重试保存' : '保存任务'}</button></div>
        </form>}
      </section>
    </main>
  </div>
}
