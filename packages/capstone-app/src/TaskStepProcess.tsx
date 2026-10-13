import { useEffect, useState, type ReactNode } from 'react'
import type { EventEnvelope } from './threadProtocol'

export type TaskStep = { id: string; number: number; title: string; status: 'running' | 'completed'; durationMs?: number; startedAt?: string; responseMs?: number; finishReason?: string }

export type StepFoldCommand = { open: boolean; revision: number }
export function toolExecutionMs(calls: readonly { startedAt?: string; durationMs?: number }[]): number | undefined {
  if (!calls.length || calls.some(call => !call.startedAt || call.durationMs === undefined)) return undefined
  const spans = calls.map(call => { const start = Date.parse(call.startedAt!); return [start, start + call.durationMs!] }).sort((a, b) => a[0] - b[0])
  if (spans.some(([start, end]) => !Number.isFinite(start) || end < start)) return undefined
  let total = 0, end = -Infinity
  for (const [start, finish] of spans) { total += Math.max(0, finish - Math.max(start, end)); end = Math.max(end, finish) }
  return total
}
export function readStepOpen(storageKey: string, id: string): boolean {
  try { return localStorage.getItem(`capstone-step-open:${storageKey}:${id}`) !== 'false' } catch { return true }
}
export function saveStepOpen(storageKey: string, id: string, open: boolean): void {
  try { localStorage.setItem(`capstone-step-open:${storageKey}:${id}`, String(open)) } catch { /* Page state still retains the choice. */ }
}

export function projectTaskSteps(events: readonly EventEnvelope[], attemptId: string): TaskStep[] {
  const steps = new Map<string, TaskStep>()
  for (const event of events) {
    if (event.attemptId !== attemptId) continue
    const values = [...(Array.isArray(event.payload.task_steps) ? event.payload.task_steps : []), event.payload.task_step]
    for (const value of values) {
      if (!value || typeof value !== 'object' || Array.isArray(value)) continue
      const record = value as Record<string, unknown>
      if (typeof record.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(record.id) ||
        !Number.isSafeInteger(record.number) || Number(record.number) < 1 || typeof record.title !== 'string' ||
        record.title.length === 0 || record.title.length > 1000 || !['running', 'completed'].includes(String(record.status))) continue
      const duration = record.duration_ms
      steps.set(record.id, { id: record.id, number: record.number as number, title: record.title,
        startedAt: steps.get(record.id)?.startedAt ?? event.occurredAt,
        ...(typeof record.response_ms === 'number' && record.response_ms >= 0 ? { responseMs: record.response_ms } : {}),
        ...(typeof record.finish_reason === 'string' ? { finishReason: record.finish_reason } : {}),
        status: record.status as TaskStep['status'], ...(typeof duration === 'number' && Number.isSafeInteger(duration) && duration >= 0 ? { durationMs: duration } : {}) })
    }
  }
  return [...steps.values()].sort((left, right) => left.number - right.number)
}

function Step({ step, storageKey, running, foldCommand, onFoldChange, toolCount, toolMs, children }: { step: TaskStep; storageKey: string; running: boolean; foldCommand?: StepFoldCommand; onFoldChange?: (id: string, open: boolean) => void; toolCount?: number; toolMs?: number; children: ReactNode }) {
  const [open, setOpen] = useState(() => readStepOpen(storageKey, step.id))
  useEffect(() => {
    if (foldCommand) setOpen(foldCommand.open)
  }, [foldCommand])
  useEffect(() => { onFoldChange?.(step.id, open) }, [onFoldChange, step.id, open])
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (!running || step.status !== 'running') return
    const timer = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [running, step.status])
  const start = step.startedAt ? Date.parse(step.startedAt) : NaN
  const elapsed = step.durationMs ?? (running && step.status === 'running' && Number.isFinite(start) ? Math.max(0, now - start) : undefined)
  return <details className="capstone-business-step" open={open}>
    <summary onClick={event => {
      event.preventDefault()
      const next = !open
      setOpen(next)
      saveStepOpen(storageKey, step.id, next)
      onFoldChange?.(step.id, next)
    }}><span className="capstone-step-number">{String(step.number).padStart(2, '0')}</span>
      <span className="capstone-chat-activity-source" data-owner="capstone">CAPSTONE</span>
      <span className="capstone-step-title">{step.title}</span>
      <span className="capstone-step-metrics">
      <small title="步骤总耗时">{elapsed === undefined ? '' : `${(elapsed / 1000).toFixed(1)}s`}{step.finishReason === 'interrupted' ? ' · 已中断' : step.status === 'completed' ? '' : running ? ' · 执行中' : '任务已结束 · 步骤未报告结束'}</small>
      {toolCount !== undefined && toolCount > 0 && <small title="工具调用数量及执行时间；并行区间只计一次">· 工具 {toolCount}次{toolMs === undefined ? '' : `/${(toolMs / 1000).toFixed(1)}s`}</small>}
      {step.responseMs !== undefined && <small title="模型响应耗时">· LLM {(step.responseMs / 1000).toFixed(1)}s</small>}
      </span>
    </summary>
    <div className="capstone-step-tools">{children}</div>
  </details>
}

export default function TaskStepProcess({ steps, storageKey, running, renderTools, toolCount, toolMs, foldCommand, onFoldChange }: { steps: readonly TaskStep[]; storageKey: string; running: boolean; renderTools: (id: string) => ReactNode; toolCount?: (id: string) => number; toolMs?: (id: string) => number | undefined; foldCommand?: StepFoldCommand; onFoldChange?: (id: string, open: boolean) => void }) {
  return <div className="capstone-business-steps" aria-label="任务步骤">{steps.map(step =>
    <Step key={`${storageKey}:${step.id}`} step={step} storageKey={storageKey} running={running} foldCommand={foldCommand} onFoldChange={onFoldChange} toolCount={toolCount?.(step.id)} toolMs={toolMs?.(step.id)}>{renderTools(step.id)}</Step>)}</div>
}
