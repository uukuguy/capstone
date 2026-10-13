import { useState, type ReactNode } from 'react'
import type { EventEnvelope } from './threadProtocol'

export type TaskStep = { id: string; number: number; title: string; status: 'running' | 'completed'; durationMs?: number; startedAt?: string }

export function projectTaskSteps(events: readonly EventEnvelope[], attemptId: string): TaskStep[] {
  const steps = new Map<string, TaskStep>()
  for (const event of events) {
    if (event.attemptId !== attemptId) continue
    const value = event.payload.task_step
    if (!value || typeof value !== 'object' || Array.isArray(value)) continue
    const record = value as Record<string, unknown>
    if (typeof record.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(record.id) ||
      !Number.isSafeInteger(record.number) || Number(record.number) < 1 || typeof record.title !== 'string' ||
      record.title.length === 0 || record.title.length > 1000 || !['running', 'completed'].includes(String(record.status))) continue
    const duration = record.duration_ms
    steps.set(record.id, { id: record.id, number: record.number as number, title: record.title,
      startedAt: steps.get(record.id)?.startedAt ?? event.occurredAt,
      status: record.status as TaskStep['status'], ...(typeof duration === 'number' && Number.isSafeInteger(duration) && duration >= 0 ? { durationMs: duration } : {}) })
  }
  return [...steps.values()].sort((left, right) => left.number - right.number)
}

function Step({ step, storageKey, running, last, toolCount, children }: { step: TaskStep; storageKey: string; running: boolean; last: boolean; toolCount?: number; children: ReactNode }) {
  const key = `capstone-step-open:${storageKey}:${step.id}`
  const [manualOpen, setManualOpen] = useState<boolean | undefined>(() => {
    try { const saved = localStorage.getItem(key); return saved === 'true' ? true : saved === 'false' ? false : undefined } catch { return undefined }
  })
  const open = manualOpen ?? (last || (running && step.status === 'running'))
  return <details className="capstone-business-step" open={open} onToggle={event => {
    const next = event.currentTarget.open
    if (next === open) return
    setManualOpen(next)
    try { localStorage.setItem(key, String(next)) } catch { /* The current page still retains the choice. */ }
  }}>
    <summary><span className="capstone-step-number">{String(step.number).padStart(2, '0')}</span>
      <span className="capstone-chat-activity-source" data-owner="capstone">CAPSTONE</span>
      <span className="capstone-step-title">{step.title}</span>
      {toolCount !== undefined && <small>{toolCount} 次工具调用</small>}
      <small>{step.status === 'completed' ? '已结束' : running ? '执行中' : '任务已结束 · 步骤未报告结束'}{step.durationMs === undefined ? '' : ` · ${(step.durationMs / 1000).toFixed(1)}s`}</small>
    </summary>
    <div className="capstone-step-tools">{children}</div>
  </details>
}

export default function TaskStepProcess({ steps, storageKey, running, renderTools, toolCount, lastStepId = steps.at(-1)?.id }: { steps: readonly TaskStep[]; storageKey: string; running: boolean; renderTools: (id: string) => ReactNode; toolCount?: (id: string) => number; lastStepId?: string }) {
  return <div className="capstone-business-steps" aria-label="任务步骤">{steps.map(step =>
    <Step key={`${storageKey}:${step.id}`} step={step} storageKey={storageKey} running={running} last={step.id === lastStepId} toolCount={toolCount?.(step.id)}>{renderTools(step.id)}</Step>)}</div>
}
