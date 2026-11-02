import {exceedsCapacity} from './applicationCapacity'
import { useEffect, useId, useState, type ReactNode } from 'react'
import { CircleHelp, Target, GitBranch, ArrowRight } from 'lucide-react'
import type { EventEnvelope } from './threadProtocol'
import type { ResearchBranch } from './taskProgress'
import MarkdownContent from './MarkdownContent'
import ProcessStepRecord from './ProcessStepRecord'
import './taskStepProcess.css'

const taskStepStatuses = ['running', 'completed', 'partial', 'failed', 'limited', 'cancelled'] as const
export type TaskStep = { id: string; number: number; title: string; status: typeof taskStepStatuses[number]; durationMs?: number; startedAt?: string; responseMs?: number; finishReason?: string; afterFailedSteps?: readonly string[]; questions?: readonly string[]; expectedOutputs?: readonly string[]; derivedFrom?: readonly string[]; resultSummary?: string; nextActionReason?: string }
const terminalLabels: Record<Exclude<TaskStep['status'], 'running'>, string> = {
  completed: '已完成', partial: '部分完成', failed: '失败', limited: '受限', cancelled: '已取消',
}

export function StepErrorDetails({ label, reason }: { label: string; reason: string }) {
  return <details className="capstone-step-transition-error" role="status">
    <summary title={label}>{label}</summary>
    <div className="capstone-step-error-reason">{reason}</div>
  </details>
}

export type StepFoldCommand = { open: boolean; revision: number }
export { toolExecutionMs } from './processTiming'
export function readStepOpen(storageKey: string, id: string): boolean {
  try { return localStorage.getItem(`capstone-step-open:${storageKey}:${id}`) === 'true' } catch { return false }
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
        record.title.length === 0 || exceedsCapacity(record.title.length,'research_progress_chars') || !taskStepStatuses.some(status => status === record.status)) continue
      const duration = record.duration_ms
      const previous = steps.get(record.id)
      const texts = (value: unknown): string[] | undefined => Array.isArray(value) &&
        !exceedsCapacity(value.length, 'research_question_count') && value.every(item => typeof item === 'string' && item.trim().length > 0 && !exceedsCapacity(item.length, 'research_text_chars')) ? value : undefined
      const text = (value: unknown) => typeof value === 'string' && value.trim().length > 0 && !exceedsCapacity(value.length, 'research_text_chars') ? value : undefined
      steps.set(record.id, { id: record.id, number: record.number as number, title: record.title,
        startedAt: steps.get(record.id)?.startedAt ?? event.occurredAt,
        ...(typeof record.response_ms === 'number' && record.response_ms >= 0 ? { responseMs: record.response_ms } : {}),
        ...(typeof record.finish_reason === 'string' ? { finishReason: record.finish_reason } : {}),
        ...(Array.isArray(record.after_failed_steps) ? { afterFailedSteps: record.after_failed_steps.filter((id): id is string => typeof id === 'string') } : {}),
        questions: texts(record.questions) ?? previous?.questions,
        expectedOutputs: texts(record.expected_outputs) ?? previous?.expectedOutputs,
        derivedFrom: texts(record.derived_from) ?? previous?.derivedFrom,
        resultSummary: text(record.result_summary) ?? previous?.resultSummary,
        nextActionReason: text(record.next_action_reason) ?? previous?.nextActionReason,
        status: record.status as TaskStep['status'], ...(typeof duration === 'number' && Number.isSafeInteger(duration) && duration >= 0 ? { durationMs: duration } : {}) })
    }
  }
  return [...steps.values()].sort((left, right) => left.number - right.number)
}

export function ResearchDetails({ step, expanded = false }: { step: Pick<TaskStep, 'questions' | 'expectedOutputs' | 'nextActionReason' | 'derivedFrom'>; expanded?: boolean }) {
  const id = useId()
  const [opened, setOpened] = useState<ReadonlySet<string>>(() => new Set(expanded ? ['questions', 'expected', 'next', 'derived'] : []))
  const fields = [
    { key: 'questions', label: '研究问题', icon: CircleHelp, values: step.questions },
    { key: 'expected', label: '预期结果', icon: Target, values: step.expectedOutputs },
    { key: 'next', label: '下一步理由', icon: ArrowRight, values: step.nextActionReason ? [step.nextActionReason] : [] },
    { key: 'derived', label: '关联发现', icon: GitBranch, values: step.derivedFrom },
  ].filter(field => field.values?.length)
  if (!fields.length) return null
  return <div className="capstone-step-research">
    <div className="capstone-step-research-controls" role="group" aria-label="研究细节">{fields.map(field => <button key={field.key} type="button" title={field.label} aria-label={field.label} aria-expanded={opened.has(field.key)} aria-controls={`${id}-${field.key}`} onClick={() => setOpened(previous => {
      const next = new Set(previous); if (next.has(field.key)) next.delete(field.key); else next.add(field.key); return next
    })}><field.icon aria-hidden="true" /></button>)}</div>
    {fields.filter(field => opened.has(field.key)).map(field => <div id={`${id}-${field.key}`} key={field.key} className="capstone-step-research-field"><span>{field.label}</span><ul>{field.values!.map((text, index) => <li key={index}>{field.key === 'derived' ? <code>{text}</code> : text}</li>)}</ul></div>)}
  </div>
}

export function RecordedResult({ text, title }: { text: string; title: string }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const paragraph = text.split(/\n\s*\n/).find(part => part.trim() && !/^\s*#{1,6}\s/.test(part)) ?? text
  const plain = paragraph.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[*`#]/g, '').replace(/\s+/g, ' ').trim()
  const characters = Array.from(plain)
  const excerpt = characters.length > 180 ? characters.slice(0, 180).join('') + '…' : plain
  const detailed = characters.length > 180 || text.trim() !== paragraph.trim() || /(?:[*`#]|\n\s*[-|])/.test(text)
  return <div className="capstone-recorded-result">
    <p className="capstone-result-excerpt">{excerpt}</p>
    {detailed && <><button type="button" className="capstone-result-toggle" aria-label={`${open ? '收起' : '查看'}详细结果：${title}`} aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>{open ? '收起详细结果' : '查看详细结果'}</button>
      {open && <div id={id} className="capstone-result-body" role="region" aria-label={`详细结果：${title}`}><MarkdownContent>{text}</MarkdownContent></div>}</>}
  </div>
}

function Step({ step, storageKey, running, expandedResearch, foldCommand, onFoldChange, toolCount, toolMs, branchToolCount = 0, hasBranches = false, branchResponses = [], stepNumbers, progress, children }: { step: TaskStep; storageKey: string; running: boolean; expandedResearch?: boolean; foldCommand?: StepFoldCommand; onFoldChange?: (id: string, open: boolean) => void; toolCount?: number; toolMs?: number; branchToolCount?: number; hasBranches?: boolean; branchResponses?: readonly number[]; stepNumbers?: Readonly<Record<string, number>>; progress?: ReactNode; children: ReactNode }) {
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (!running || step.status !== 'running') return
    const timer = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [running, step.status])
  const start = step.startedAt ? Date.parse(step.startedAt) : NaN
  const elapsed = step.durationMs ?? (running && step.status === 'running' && Number.isFinite(start) ? Math.max(0, now - start) : undefined)
  return <section className="capstone-business-step-record" data-step-id={step.id}>
    <ProcessStepRecord id={step.id} title={step.title} storageKey={storageKey} resultSummary={step.resultSummary} defaultExpanded={expandedResearch} foldCommand={foldCommand} onFoldChange={onFoldChange} headingClassName="capstone-step-heading" heading={<><span className="capstone-step-number">{String(step.number).padStart(2, '0')}</span>
      <span className="capstone-chat-activity-source" data-owner="capstone">CAPSTONE</span>
      <span className="capstone-step-title">{step.title}{Boolean(step.afterFailedSteps?.length) && <small className="capstone-step-continuation" title="此前步骤有工具调用失败，本步继续处理；方法调整以智能体公开记录为准">接续 {step.afterFailedSteps!.map(id => stepNumbers?.[id]).filter(number => number !== undefined).map(number => String(number).padStart(2, '0')).join('、') || '失败'}</small>}</span>
      <span className="capstone-step-metrics">
      <small title="步骤总耗时">{elapsed === undefined ? '' : `${(elapsed / 1000).toFixed(1)}s`}{step.status !== 'running' ? <span> · {terminalLabels[step.status]}</span> : step.finishReason === 'interrupted' ? ' · 已中断' : running ? ' · 执行中' : '任务已结束 · 步骤未报告结束'}</small>
      {(toolCount !== undefined || branchToolCount > 0) && (toolCount ?? 0) + branchToolCount > 0 && <small title={hasBranches ? `本步工具 ${toolCount ?? 0} 次，分支工具 ${branchToolCount} 次；不将委派等待时间作为子工具执行时间` : '工具调用数量及执行时间；并行区间只计一次'}>· 工具 {(toolCount ?? 0) + branchToolCount}次{hasBranches || toolMs === undefined ? '' : `/${(toolMs / 1000).toFixed(1)}s`}</small>}
      {step.responseMs !== undefined ? <small title={hasBranches ? '仅主流程模型响应耗时；分支另列，不能据此判断并行总耗时' : '模型响应耗时'}>· {hasBranches ? '主流程 LLM' : 'LLM'} {(step.responseMs / 1000).toFixed(1)}s</small> : <small title="宿主未保存步骤模型响应耗时">· LLM 未记录</small>}
      {hasBranches && <small title="各分支已完成模型响应的累计耗时；并行响应相加不等于实际等待时间">· 分支 LLM {branchResponses.length ? `${branchResponses.length}次/${(branchResponses.reduce((sum, ms) => sum + ms, 0) / 1000).toFixed(1)}s` : "未记录"}</small>}
      </span>
    </>}>
    <div className="capstone-step-description">
      {step.resultSummary && <div><span>结果摘录</span><RecordedResult text={step.resultSummary} title={step.title} /></div>}
    </div>
    <ResearchDetails step={step} expanded={expandedResearch} />
    {progress}
    <details className="capstone-business-step">
      <summary aria-label={`工具明细：${step.title}`}>工具明细</summary>
      <div className="capstone-step-tools">{children}</div>
    </details>
    </ProcessStepRecord>
  </section>
}

function Branch({ branch, storageKey, expandedResearch }: { branch: ResearchBranch; storageKey: string; expandedResearch?: boolean }) {
  const key = `branch:${branch.id}`
  const [open, setOpen] = useState(() => readStepOpen(storageKey, key))
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (branch.status !== 'running' || !branch.startedAt) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [branch.status, branch.startedAt])
  const start = branch.startedAt ? Date.parse(branch.startedAt) : NaN
  const elapsed = branch.durationMs ?? (branch.status === 'running' && Number.isFinite(start) ? Math.max(0, now - start) : undefined)
  const labels = { running: '执行中', completed: '子执行完成，待综合评估', failed: '执行失败', cancelled: '已取消', unknown: '结束状态未记录' }
  return <section className="capstone-research-branch" aria-label={`子分支：${branch.title}`}>
    <p className="capstone-research-branch-title">{branch.title}<small title="子分支从实际启动到结束的耗时；并行分支耗时不可直接相加作为任务总耗时">{elapsed !== undefined && `${(elapsed / 1000).toFixed(1)}s · `}{labels[branch.status]}</small>{branch.responses && <small title="已完成模型响应的累计耗时">LLM {Object.keys(branch.responses).length}次/{(Object.values(branch.responses).reduce((sum, ms) => sum + ms, 0) / 1000).toFixed(1)}s</small>}</p>
    <ResearchDetails step={{ questions: branch.questions, expectedOutputs: branch.expectedOutputs }} expanded={expandedResearch} />
    {branch.resultSummary && <RecordedResult text={branch.resultSummary} title={branch.title} />}
    {branch.error && <details><summary>子分支失败原因</summary><p>{branch.error}</p></details>}
    {branch.tools.length > 0 && <details open={open}><summary onClick={event => {
      event.preventDefault(); setOpen(!open); saveStepOpen(storageKey, key, !open)
    }}>子分支工具明细 · {branch.tools.length} 次</summary><ul>{branch.tools.map(tool => <li key={tool.id}>{tool.operation || tool.name} · {tool.status === 'failed' ? '失败' : tool.status === 'completed' ? '调用完成' : '执行中'}{tool.output && <details><summary>返回摘要</summary><p>{tool.output}</p></details>}</li>)}</ul></details>}
  </section>
}

export function ResearchBranchItems({ branches, storageKey, expandedResearch }: { branches: readonly ResearchBranch[]; storageKey: string; expandedResearch?: boolean }) {
  return <>{branches.map(branch => <Branch key={`${storageKey}:${branch.id}`} branch={branch} storageKey={storageKey} expandedResearch={expandedResearch} />)}</>
}

export default function TaskStepProcess({ steps, storageKey, running, expandedResearch = false, renderTools, renderProgress, branches = [], toolCount, toolMs, stepNumbers, foldCommand, onFoldChange }: { steps: readonly TaskStep[]; storageKey: string; running: boolean; expandedResearch?: boolean; renderTools: (id: string) => ReactNode; renderProgress?: (id: string) => ReactNode; branches?: readonly ResearchBranch[]; toolCount?: (id: string) => number; toolMs?: (id: string) => number | undefined; stepNumbers?: Readonly<Record<string, number>>; foldCommand?: StepFoldCommand; onFoldChange?: (id: string, open: boolean) => void }) {
  return <div className="capstone-business-steps" aria-label="任务步骤">{steps.map(step =>
    <Step key={`${storageKey}:${step.id}`} step={step} storageKey={storageKey} running={running} expandedResearch={expandedResearch} foldCommand={foldCommand} onFoldChange={onFoldChange} toolCount={toolCount?.(step.id)} toolMs={toolMs?.(step.id)} branchToolCount={branches.filter(branch => branch.parentStepId === step.id).reduce((sum, branch) => sum + branch.tools.length, 0)} hasBranches={branches.some(branch => branch.parentStepId === step.id)} branchResponses={branches.filter(branch => branch.parentStepId === step.id).flatMap(branch => Object.values(branch.responses ?? {}))} stepNumbers={stepNumbers} progress={<>{renderProgress?.(step.id)}<ResearchBranchItems expandedResearch={expandedResearch} branches={branches.filter(branch => branch.parentStepId === step.id)} storageKey={storageKey} /></>}>{renderTools(step.id)}</Step>)}</div>
}
