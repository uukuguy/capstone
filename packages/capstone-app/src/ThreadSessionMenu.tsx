import { useEffect, useRef, useState } from 'react'
import { Archive, ArchiveRestore, History, Plus, X } from 'lucide-react'
import type { HttpThreadTransport } from './threadHttpTransport'
import type { ThreadDescriptor } from './threadManagement'

function sessionTime(value: string): string {
  const date = new Date(value)
  return date.toDateString() === new Date().toDateString()
    ? `今天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })}`
    : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

export default function ThreadSessionMenu({ transport, threadId, onNew, onSelect, onArchived, creating }: {
  transport: HttpThreadTransport; threadId: string; creating: boolean
  onNew: () => void; onSelect: (threadId: string) => void; onArchived: (archived: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const [archived, setArchived] = useState(false)
  const [threads, setThreads] = useState<ThreadDescriptor[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [revision, refresh] = useState(0)
  const controller = useRef<AbortController | null>(null)
  const mutation = useRef<AbortController | null>(null)
  const menu = useRef<HTMLElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)

  useEffect(() => () => mutation.current?.abort(), [])

  useEffect(() => {
    if (!open) return
    const abort = new AbortController(); controller.current = abort
    setBusy(true); setError(null); setThreads([]); setCursor(null)
    void transport.listThreads(archived, undefined, abort.signal, threadId).then((page) => {
      if (!abort.signal.aborted) { setThreads(page.threads); setCursor(page.nextBeforeThreadId) }
    }).catch(() => {
      if (!abort.signal.aborted) setError('暂时无法加载会话，请稍后重试。')
    }).finally(() => { if (!abort.signal.aborted) setBusy(false) })
    return () => abort.abort()
  }, [transport, archived, open, revision, threadId])

  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!menu.current?.contains(event.target as Node)) setOpen(false) }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); trigger.current?.focus() }
    }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [open])

  async function more() {
    const abort = controller.current
    if (!cursor || busy || !abort || abort.signal.aborted) return
    setBusy(true); setError(null)
    try {
      const page = await transport.listThreads(archived, cursor, abort.signal, threadId)
      if (!abort.signal.aborted) { setThreads((previous) => [...previous, ...page.threads.filter((row) => !previous.some((item) => item.threadId === row.threadId))]); setCursor(page.nextBeforeThreadId) }
    } catch { if (!abort.signal.aborted) setError('暂时无法加载会话，请稍后重试。') }
    finally { if (!abort.signal.aborted) setBusy(false) }
  }

  async function toggle(row: ThreadDescriptor) {
    if (busy) return
    // Closing the list cancels reads, but an admitted archive/restore must
    // still update the current conversation's Composer state.
    const abort = new AbortController(); mutation.current = abort
    setBusy(true); setError(null)
    try {
      const result = await transport.archiveThread(row.threadId, !row.archived, abort.signal)
      if (!abort.signal.aborted) {
        if (row.threadId === threadId) onArchived(result.archived)
        refresh((value) => value + 1)
      }
    } catch (cause) {
      if (!abort.signal.aborted) setError(cause instanceof Error && 'status' in cause && cause.status === 409
        ? '请先完成或停止当前任务，再归档对话。' : '操作未完成，请稍后重试。')
    } finally { if (!abort.signal.aborted) setBusy(false) }
  }

  return <nav ref={menu} className="thread-session-menu" aria-label="会话管理">
    <div className="thread-session-actions">
      <button type="button" aria-label={creating ? '正在新建…' : '新建对话'} disabled={creating} onClick={() => { setOpen(false); onNew() }}><Plus size={17} aria-hidden="true" /><span>{creating ? '正在新建…' : '新建对话'}</span></button>
      <button ref={trigger} type="button" aria-label="会话列表" aria-expanded={open} onClick={() => setOpen((value) => !value)}><History size={17} aria-hidden="true" /><span>会话列表</span></button>
    </div>
    {open && <section className="thread-session-panel" aria-label="会话列表">
      <div className="thread-session-panel-heading"><span>我的对话</span><button type="button" className="thread-session-icon" aria-label="关闭会话列表" onClick={() => { setOpen(false); trigger.current?.focus() }}><X size={17} /></button></div>
      <div className="thread-session-tabs"><button type="button" aria-pressed={!archived} onClick={() => setArchived(false)}>最近对话</button><button type="button" aria-pressed={archived} onClick={() => setArchived(true)}>已归档</button></div>
      <div className="thread-session-scroll">
        {error && <p role="alert">{error}<button type="button" onClick={() => refresh((value) => value + 1)}>重试</button></p>}
        {!busy && !error && threads.length === 0 && <p className="thread-session-empty">暂无{archived ? '已归档' : ''}对话。</p>}
        <ul>{threads.map((row) => <li key={row.threadId} className={row.threadId === threadId ? 'is-current' : undefined}>
          <button type="button" className="thread-session-select" aria-current={row.threadId === threadId ? 'page' : undefined} title={row.title || '新对话'} onClick={() => { onSelect(row.threadId); setOpen(false) }}>
            <span className="thread-session-title">{row.title || '新对话'}{row.threadId === threadId && <small className="thread-session-current">当前</small>}</span>
            <span className="thread-session-summary">{row.modelId}<time dateTime={row.createdAt}>{sessionTime(row.createdAt)}</time></span>
          </button>
          <button type="button" className="thread-session-icon" disabled={busy} onClick={() => void toggle(row)} title={row.archived ? '恢复对话' : '归档对话'} aria-label={`${row.archived ? '恢复' : '归档'} ${row.threadId}`}>{row.archived ? <ArchiveRestore size={17} /> : <Archive size={17} />}</button>
        </li>)}</ul>
        {busy && <p role="status">正在加载…</p>}
        {cursor && <button className="thread-session-more" type="button" disabled={busy} onClick={() => void more()}>加载更多</button>}
      </div>
      <p className="thread-session-footer">归档后仍可查看和恢复。</p>
    </section>}
  </nav>
}
