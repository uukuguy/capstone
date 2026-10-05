import { useEffect, useRef, useState } from 'react'
import type { HttpThreadTransport } from './threadHttpTransport'
import type { ThreadDescriptor } from './threadManagement'

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
  useEffect(() => {
    if (!open) return
    const abort = new AbortController(); controller.current = abort
    setBusy(true); setError(null); setThreads([]); setCursor(null)
    void transport.listThreads(archived, undefined, abort.signal).then((page) => {
      if (!abort.signal.aborted) { setThreads(page.threads); setCursor(page.nextBeforeThreadId) }
    }).catch((cause) => {
      if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : '会话列表暂不可用')
    }).finally(() => { if (!abort.signal.aborted) setBusy(false) })
    return () => abort.abort()
  }, [transport, archived, open, revision, threadId])

  async function more() {
    if (!cursor || busy) return
    const abort = controller.current
    if (!abort || abort.signal.aborted) return
    setBusy(true); setError(null)
    try {
      const page = await transport.listThreads(archived, cursor, abort.signal)
      if (!abort.signal.aborted) {
        setThreads((previous) => [...previous, ...page.threads.filter((row) => !previous.some((item) => item.threadId === row.threadId))])
        setCursor(page.nextBeforeThreadId)
      }
    } catch (cause) {
      if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : '加载失败')
    } finally { if (!abort.signal.aborted) setBusy(false) }
  }

  async function toggle(row: ThreadDescriptor) {
    if (busy) return
    const abort = controller.current
    if (!abort || abort.signal.aborted) return
    setBusy(true); setError(null)
    try {
      const result = await transport.archiveThread(row.threadId, !row.archived, abort.signal)
      if (!abort.signal.aborted) {
        if (row.threadId === threadId) onArchived(result.archived)
        refresh((value) => value + 1)
      }
    } catch (cause) {
      if (!abort.signal.aborted) setError(cause instanceof Error && 'status' in cause && cause.status === 409
        ? '会话仍有任务在执行，请先完成或停止任务。' : cause instanceof Error ? cause.message : '操作失败')
    } finally { if (!abort.signal.aborted) setBusy(false) }
  }

  return <nav className="thread-session-menu" aria-label="会话管理">
    <div className="thread-session-actions">
      <button type="button" className="thread-primary-button" disabled={creating} onClick={onNew}>{creating ? '正在新建…' : '新建对话'}</button>
      <button type="button" className="thread-secondary-button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>会话列表</button>
    </div>
    {open && <section className="thread-session-panel" aria-label="会话列表">
      <div className="thread-session-tabs"><button type="button" aria-pressed={!archived} onClick={() => setArchived(false)}>最近对话</button><button type="button" aria-pressed={archived} onClick={() => setArchived(true)}>已归档</button></div>
      {error && <p role="alert">{error}</p>}
      {!busy && !error && threads.length === 0 && <p>暂无{archived ? '已归档' : ''}对话。</p>}
      <ul>{threads.map((row) => <li key={row.threadId}>
        <button type="button" className="thread-session-select" aria-current={row.threadId === threadId ? 'page' : undefined} onClick={() => { onSelect(row.threadId); setOpen(false) }}>
          <strong>{row.modelId}</strong><small>{row.implementationFamily} · {new Date(row.createdAt).toLocaleString()} · {row.threadId.slice(-6)}</small>
        </button>
        <button type="button" disabled={busy} onClick={() => void toggle(row)} aria-label={`${row.archived ? '恢复' : '归档'} ${row.threadId}`}>{row.archived ? '恢复' : '归档'}</button>
      </li>)}</ul>
      {busy && <p role="status">正在加载…</p>}
      {cursor && <button type="button" disabled={busy} onClick={() => void more()}>加载更多会话</button>}
      <small>归档保留历史消息与证据，不会删除对话。</small>
    </section>}
  </nav>
}
