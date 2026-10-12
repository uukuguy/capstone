import { useState } from 'react'
import type { AttemptRecords } from './attemptRecords'
import type { EventEnvelope } from './threadProtocol'

export type AttemptRecordReader = (attemptId: string, after?: number) => Promise<AttemptRecords>

const LABELS: Record<string, string> = {
  research_step_resumed: '调整推演方式，沿用已有结果',
  tool_started: '开始调用', tool_completed: '调用结束', tool_failed: '调用失败', tool_cancelled: '调用取消',
  validation_failed: '核验未通过', research_state_updated: '研究记录已保存',
  attempt_started: '任务开始', attempt_completed: '任务结束', attempt_failed: '任务失败',
  attempt_interrupted: '任务中断', attempt_cancelled: '任务取消',
}

function visibleRecord(event: EventEnvelope): boolean {
  return event.visibility === 'public' && Object.hasOwn(LABELS, event.eventType)
}

export default function AttemptRecordPanel({ attemptId, read }: { attemptId: string; read: AttemptRecordReader }) {
  const [records, setRecords] = useState<AttemptRecords | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const load = async () => {
    if (loading) return
    setLoading(true)
    setError(false)
    try {
      let cursor = records?.nextAfter ?? 0
      let page = await read(attemptId, cursor)
      if (page.attemptId !== attemptId) throw new Error('任务记录身份不一致')
      const firstPage = page
      const events = page.events.filter(visibleRecord)
      // Skip internal-only pages without requiring a click for each stream frame page.
      // Bound each user action to eight requests; the next cursor remains available.
      for (let requests = 1; requests < 8 && page.hasMore && events.length === 0 && page.nextAfter > cursor; requests++) {
        cursor = page.nextAfter
        try {
          page = await read(attemptId, cursor)
          if (page.attemptId !== attemptId) throw new Error('任务记录身份不一致')
          events.push(...page.events.filter(visibleRecord))
        } catch { setError(true); break }
      }
      setRecords(previous => previous ? { ...previous, nextAfter: page.nextAfter, hasMore: page.hasMore,
        events: [...previous.events, ...events] } : { ...firstPage, nextAfter: page.nextAfter, hasMore: page.hasMore, events })
    } catch { setError(true) }
    finally { setLoading(false) }
  }
  return <details className="capstone-evidence-trace">
    <summary>原任务记录</summary>
    <p>原任务的执行与核验记录。读取记录不启动新计算。</p>
    {records && <>
      <strong>{records.instruction}</strong>
      {records.modelContext && <p>{records.modelContext.modelId} · 修订 {records.modelContext.modelRevision}</p>}
      <ol>{records.events.map(event => <li key={event.eventId}>
        <span>{LABELS[event.eventType]}{event.eventType === 'tool_completed' && event.payload.ok === false ? ' · 未成功' : ''}</span>
        {typeof event.payload.capability === 'string' && <code>{event.payload.capability}</code>}
        <small>事件 {event.eventSeq} · {event.occurredAt}</small>
      </li>)}</ol>
      <p>已读取到事件 {records.nextAfter}。{records.hasMore ? '还有后续记录。' : '记录读取完毕。'}</p>
    </>}
    {error && <p role="alert">任务记录暂时无法读取。已读内容保留，请重试。</p>}
    {(!records || records.hasMore) && <button type="button" disabled={loading} onClick={() => void load()}>
      {loading ? '正在读取…' : records ? '读取后续记录' : '读取原任务记录'}
    </button>}
  </details>
}
