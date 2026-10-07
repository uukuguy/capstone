import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { readDraft, writeDraft } from './threadSessionState'
import ThreadSettingsMenu, { useCloseThreadSettings } from './ThreadSettingsMenu'
import ThreadSystemNotice from './ThreadSystemNotice'
import { projectSystemNotices, type ThreadSystemNotice as SystemNotice } from './threadSystemNotices'
import { answerEvidenceState, evidenceStateCopy, type AnswerEvidenceState } from './threadEvidenceState'
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type ThreadMessageLike,
  useAui,
  useAuiState,
  useExternalStoreRuntime,
} from '@assistant-ui/react'
import { Activity, ArrowUp, Check, ChevronRight, ChevronUp, Copy, FileCheck2, ListTree, Network, MoreHorizontal, Pencil, RotateCcw, Square, ThumbsDown, ThumbsUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { EventEnvelope, ResultProjection } from './threadProtocol'
import type { CaseActionSnapshot, CaseExecutionSnapshot } from './threadProtocol'
import type { ThreadTransportState } from './threadClient'
import type { ThreadCatalogCase } from './threadCatalog'
import { attemptFailureCopy } from './threadFeedback'

type SendMode = 'automatic' | 'ordinary' | 'professional'

const AnswerReadingContext = createContext<{
  collapsed: ReadonlySet<string>
  toggle: (id: string) => void
  restoreAnchor: (id: string) => void
}>({ collapsed: new Set(), toggle: () => {}, restoreAnchor: () => {} })

const ChatMessageContext = createContext<Parameters<typeof ChatMessage>[0] | null>(null)

function ThreadChatMessage() {
  const props = useContext(ChatMessageContext)
  return props ? <ChatMessage {...props} /> : null
}

const EMPTY_PROMPTS = [
  '有哪些 PyPSA 的电网模型？',
  '有哪些 pandapower 的电网模型？',
  'IEEE-39 有哪些母线和线路？',
  '对 IEEE-39 执行一次交流潮流。',
  '筛查负载率最高的三条线路。',
] as const

export type ChatActivity = {
  id: string
  label: string
  source: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  startedAt?: string
  finishedAt?: string
  durationMs?: number
}

const TOOL_LABELS: Record<string, string> = {
  grid_model_list: '读取模型目录',
  grid_context_get: '读取模型上下文',
  grid_context_open: '打开模型上下文',
  grid_model_element_get: '读取模型元件',
  grid_topology_branch_endpoints: '解析线路端点',
  grid_model_constraints_describe: '获取模型约束',
  grid_model_dataset_list: '获取模型数据集',
  grid_environment_describe: '读取运行环境',
  grid_guide_open: '读取分析指南',
}

function toolName(event: EventEnvelope): string {
  return typeof event.payload.tool_name === 'string'
    ? event.payload.tool_name
    : typeof event.payload.capability === 'string' ? event.payload.capability : event.eventType
}

function activityId(event: EventEnvelope): string {
  return typeof event.payload.tool_call_id === 'string' ? event.payload.tool_call_id : toolName(event)
}

function activitySource(event: EventEnvelope): string {
  const binding = typeof event.payload.binding_id === 'string' ? event.payload.binding_id : 'capstone'
  const capability = typeof event.payload.capability === 'string' ? event.payload.capability : toolName(event)
  return `${binding} · ${capability}`
}

export function projectAssistantActivity(events: readonly EventEnvelope[]): ChatActivity[] {
  const grouped = new Map<string, ChatActivity>()
  for (const event of events) {
    if (!['tool_started', 'tool_completed', 'tool_failed', 'tool_cancelled'].includes(event.eventType)) continue
    const id = activityId(event)
    const previous = grouped.get(id)
    const status = event.eventType === 'tool_started'
      ? 'running'
      : event.eventType === 'tool_failed' || event.payload.ok === false ? 'failed' : event.eventType === 'tool_cancelled' ? 'cancelled' : 'completed'
    const startedAt = previous?.startedAt || (event.eventType === 'tool_started' ? event.occurredAt : undefined)
    grouped.set(id, {
      id,
      label: typeof event.payload.tool_name === 'string' || typeof event.payload.capability === 'string' ? TOOL_LABELS[toolName(event)] || toolName(event).replaceAll('_', ' ') : previous?.label || toolName(event),
      source: typeof event.payload.binding_id === 'string' || typeof event.payload.capability === 'string' ? activitySource(event) : previous?.source || activitySource(event),
      status,
      ...(startedAt ? { startedAt } : {}),
      ...((event.eventType === 'tool_started' ? previous?.finishedAt : event.occurredAt) ? { finishedAt: event.eventType === 'tool_started' ? previous?.finishedAt : event.occurredAt } : {}),
      ...((event.eventType === 'tool_started' ? previous?.durationMs : durationBetween(startedAt, event.occurredAt)) !== undefined ? { durationMs: event.eventType === 'tool_started' ? previous?.durationMs : durationBetween(startedAt, event.occurredAt) } : {}),
    })
  }
  const terminal = [...events].reverse().find((event) => ['attempt_failed', 'attempt_cancelled', 'attempt_interrupted', 'attempt_completed'].includes(event.eventType))
  if (terminal && terminal.eventType !== 'attempt_completed') {
    const terminalStatus = terminal.eventType === 'attempt_cancelled' || terminal.eventType === 'attempt_interrupted' ? 'cancelled' : 'failed'
    for (const [id, item] of grouped) {
      if (item.status === 'running') grouped.set(id, { ...item, status: terminalStatus, finishedAt: terminal.occurredAt, durationMs: durationBetween(item.startedAt, terminal.occurredAt) })
    }
  }
  return [...grouped.values()]
}

function payloadText(event: EventEnvelope, nested = false): string {
  const source = nested && event.payload.payload && typeof event.payload.payload === 'object' && !Array.isArray(event.payload.payload)
    ? event.payload.payload as Record<string, unknown>
    : event.payload
  const value = source.text
  return typeof value === 'string' ? value : ''
}

function commandMode(event: EventEnvelope): SendMode {
  if (event.payload.kind === 'send_professional') return 'professional'
  if (event.payload.kind === 'send_auto') return 'automatic'
  return 'ordinary'
}

function stringRefs(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.length > 0) : []
}

function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${Math.max(0, Math.round(durationMs))}ms`
  const seconds = durationMs / 1000
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${(seconds - minutes * 60).toFixed(0).padStart(2, '0')}s`
}

function caseStatusLabel(execution: CaseExecutionSnapshot): string {
  if (execution.status === 'completed') {
    const duration = execution.steps.reduce((total, step) => total + (step.durationMs || 0), 0)
    return `案例已完成 · ${execution.completedSteps} / ${execution.totalSteps} 步${duration > 0 ? ` · 总运行时长 ${formatDuration(duration)}` : ''}`
  }
  if (execution.status === 'cancelled') return `案例已停止 · ${execution.completedSteps} / ${execution.totalSteps} 步`
  if (execution.status === 'blocked') return `案例执行受阻 · ${execution.completedSteps} / ${execution.totalSteps} 步`
  if (execution.status === 'idle') return '准备开始案例'
  return `案例执行中 · ${execution.completedSteps} / ${execution.totalSteps}`
}

function caseStepDuration(step: CaseExecutionSnapshot['steps'][number], running: boolean): number | undefined {
  if (step.durationMs !== null) return step.durationMs
  if (!running) return undefined
  const details = step.details
  const started = typeof details.startedAt === 'string' ? details.startedAt : typeof details.started_at === 'string' ? details.started_at : undefined
  return started ? durationBetween(started, new Date().toISOString()) : undefined
}

function CaseStepDuration({ step, running }: { step: CaseExecutionSnapshot['steps'][number]; running: boolean }) {
  const [, tick] = useState(0)
  useEffect(() => {
    if (!running || step.durationMs !== null) return undefined
    const timer = window.setInterval(() => tick((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [running, step.durationMs])
  const elapsed = caseStepDuration(step, running)
  return elapsed === undefined ? null : <small className="thread-case-step-duration">{running ? '运行中' : '运行'} {formatDuration(elapsed)}</small>
}

export type ThreadCaseProgressProps = {
  execution: CaseExecutionSnapshot
  connection?: ThreadTransportState | 'connecting'
  onAction: (actionId: CaseActionSnapshot['actionId']) => void
}

/** Compact, shared Case lifecycle projection for the Thread conversation. */
export function ThreadCaseProgress({ execution, connection = 'live', onAction }: ThreadCaseProgressProps) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const resync = connection === 'resync_required'
  const connectionReason = resync ? '先重新同步 Thread 后才能操作案例' : undefined
  const currentStep = execution.currentStep === null ? undefined : execution.steps[execution.currentStep - 1]
  return <section className={`thread-case-progress is-${execution.status}${resync ? ' is-resync' : ''}`} aria-label="案例执行">
    <div className="thread-case-heading"><div><span className="eyebrow">CASE</span><strong>{execution.displayName}</strong></div><span className="thread-case-status">{caseStatusLabel(execution)}</span></div>
    {execution.status === 'blocked' && currentStep && <div className="thread-case-blocked" role="alert"><strong>步骤 {currentStep.ordinal} 未完成</strong><span>运行被中断</span>{execution.disabledReasons.map((reason) => <span key={reason}>{reason}</span>)}</div>}
    {resync && <div className="thread-case-blocked" role="status"><strong>需要重新同步</strong><span>{connectionReason}</span></div>}
    <ol className="thread-case-steps">
      {execution.steps.map((step) => <li key={step.ordinal} className={`is-${step.status}${step.ordinal === execution.currentStep ? ' is-current' : ''}`}>
        <span className="thread-case-step-mark" aria-hidden="true">{step.status === 'completed' ? '✓' : step.status === 'running' ? '●' : step.status === 'failed' || step.status === 'interrupted' ? '!' : '○'}</span>
        <span className="thread-case-step-copy"><strong>{step.title}</strong><CaseStepDuration step={step} running={step.status === 'running'} /></span>
      </li>)}
    </ol>
    {execution.disabledReasons.length > 0 && execution.status !== 'blocked' && <div className="thread-case-disabled-reasons" aria-label="案例不可用原因">{execution.disabledReasons.map((reason) => <span key={reason}>{reason}</span>)}</div>}
    <div className="thread-case-actions" aria-label="案例操作">
      {execution.actions.map((action) => <button key={action.actionId} type="button" className="thread-case-action" disabled={!action.enabled || resync} title={resync ? connectionReason : undefined} onClick={() => { if (action.actionId === 'view_case_details') setDetailsOpen(true); onAction(action.actionId) }}>{action.label}</button>)}
    </div>
    {execution.status === 'completed' && detailsOpen && <div className="thread-case-details"><div className="thread-case-detail-panel" role="region" aria-label="案例过程详情">{execution.steps.map((step) => <article key={step.ordinal}><strong>步骤 {step.ordinal} · {step.title}</strong><dl>{Object.entries(step.details).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl></article>)}</div></div>}
  </section>
}

export type ThreadCasePickerProps = {
  cases: readonly ThreadCatalogCase[]
  disabled?: boolean
  onStart: (caseId: string, caseVersion: string) => void
}

export function ThreadCasePicker({ cases, disabled = false, onStart }: ThreadCasePickerProps) {
  const [selected, setSelected] = useState(cases[0] ? `${cases[0].caseId}@${cases[0].caseVersion}` : '')
  useEffect(() => {
    if (!cases.some((item) => `${item.caseId}@${item.caseVersion}` === selected)) setSelected(cases[0] ? `${cases[0].caseId}@${cases[0].caseVersion}` : '')
  }, [cases, selected])
  const current = cases.find((item) => `${item.caseId}@${item.caseVersion}` === selected)
  if (cases.length === 0) return null
  return <section className="thread-case-picker" aria-label="注册案例"><div><span className="eyebrow">REGISTERED CASES</span><strong>选择一个案例开始</strong></div><select aria-label="注册案例" value={selected} disabled={disabled} onChange={(event) => setSelected(event.target.value)}>{cases.map((item) => <option key={`${item.caseId}@${item.caseVersion}`} value={`${item.caseId}@${item.caseVersion}`}>{item.displayName}</option>)}</select>{current && <small>{current.summary} · {current.stepCount} 步</small>}<button type="button" className="thread-case-action thread-case-start" disabled={disabled || !current} onClick={() => current && onStart(current.caseId, current.caseVersion)}>开始案例</button></section>
}

function durationBetween(startedAt: string | undefined, finishedAt: string | undefined): number | undefined {
  if (!startedAt || !finishedAt) return undefined
  const start = Date.parse(startedAt)
  const finish = Date.parse(finishedAt)
  if (!Number.isFinite(start) || !Number.isFinite(finish)) return undefined
  return Math.max(0, finish - start)
}

function terminalDetail(event: EventEnvelope): string | undefined {
  const candidates = [event.payload.message, event.payload.error, event.payload.reason]
  const detail = candidates.find((value): value is string => typeof value === 'string' && value.trim().length > 0)
  return detail?.trim()
}

function terminalContent(event: EventEnvelope): string {
  if (event.eventType === 'attempt_failed') {
    const detail = terminalDetail(event)
    const code = typeof event.payload.error_code === 'string' ? event.payload.error_code : undefined
    return `**执行失败**\n\n${detail || attemptFailureCopy(code)}${detail && code ? `\n\n诊断代码：${code}` : ''}`
  }
  if (event.eventType === 'attempt_cancelled') return '**本次 Attempt 已取消**\n\n可以修改指令后重新发送。'
  return '**本次 Attempt 已中断**\n\n可以查看运行过程，并在确认模型上下文后重新运行。'
}

export function projectAssistantMessages(events: readonly EventEnvelope[]): ThreadMessageLike[] {
  const messages: ThreadMessageLike[] = []
  const assistantByAttempt = new Map<string, ThreadMessageLike & { content: string }>()
  const instructionByAttempt = new Map<string, { text: string; mode: SendMode; messageId: string }>()
  const instructionByTurn = new Map<string, { text: string; mode: SendMode; messageId: string }>()
  const startedAtByAttempt = new Map<string, string>()
  const contextByAttempt = new Map<string, { modelContextId?: string; selectionRevision?: string }>()
  const ensureAssistant = (key: string, startedAt?: string) => {
    if (startedAt) startedAtByAttempt.set(key, startedAt)
    const existing = assistantByAttempt.get(key)
    if (existing) {
      if (startedAt) {
        const metadata = existing.metadata as { custom?: Record<string, unknown> } | undefined
        ;(existing as unknown as { metadata?: unknown }).metadata = { custom: { ...(metadata?.custom || {}), startedAt } }
      }
      return existing
    }
    const message = { id: `assistant-${key}`, role: 'assistant' as const, content: '', status: { type: 'running' as const }, metadata: { custom: { attemptId: key, source: 'capstone-harness', ...(startedAt ? { startedAt } : {}) } } }
    assistantByAttempt.set(key, message)
    messages.push(message)
    return message
  }
  for (const event of events) {
    const eventKey = event.attemptId || event.turnId
    if (eventKey && (event.modelContextId || event.selectionRevision)) {
      const previous = contextByAttempt.get(eventKey)
      contextByAttempt.set(eventKey, {
        modelContextId: event.modelContextId || previous?.modelContextId,
        selectionRevision: event.selectionRevision || previous?.selectionRevision,
      })
    }
    if (event.eventType === 'command_accepted' && (event.payload.kind === 'send_auto' || event.payload.kind === 'send_ordinary' || event.payload.kind === 'send_professional')) {
      const text = payloadText(event, true)
      if (text) {
        const key = event.attemptId || event.turnId
        const instruction = { text, mode: commandMode(event), messageId: `user-${event.eventId}` }
        if (key) instructionByAttempt.set(key, instruction)
        if (event.turnId) instructionByTurn.set(event.turnId, instruction)
        messages.push({ id: `user-${event.eventId}`, role: 'user', content: text, metadata: { custom: { mode: commandMode(event), eventId: event.eventId, attemptId: key, receipt: `${commandMode(event)} · accepted` } } })
      }
      continue
    }
    if (event.eventType === 'attempt_started') {
      const key = event.attemptId || event.turnId
      if (key) ensureAssistant(key, event.occurredAt)
      continue
    }
    if (event.eventType === 'assistant_text_delta') {
      const key = event.attemptId || event.turnId || `event-${event.eventId}`
      ensureAssistant(key).content += payloadText(event)
      continue
    }
    if (event.eventType === 'attempt_completed' || event.eventType === 'attempt_failed' || event.eventType === 'attempt_cancelled' || event.eventType === 'attempt_interrupted') {
      const key = event.attemptId || event.turnId
      let message = key ? assistantByAttempt.get(key) : undefined
      const answer = event.eventType === 'attempt_completed' && typeof event.payload.answer === 'string'
        ? event.payload.answer
        : ''
      const terminalAnswer = event.eventType === 'attempt_completed' ? answer : terminalContent(event)
      if (!message && key) message = ensureAssistant(key, key ? startedAtByAttempt.get(key) : undefined)
      const partialText = event.eventType !== 'attempt_completed' ? message?.content : undefined
      if (message && terminalAnswer && (event.eventType === 'attempt_completed' || !message.content)) {
        message.content = terminalAnswer
      } else if (message && event.eventType !== 'attempt_completed') {
        message.content += `\n\n${terminalAnswer}`
      }
      if (message) {
        const instruction = (key ? instructionByAttempt.get(key) : undefined) || (event.turnId ? instructionByTurn.get(event.turnId) : undefined)
        const status = event.eventType === 'attempt_completed'
          ? { type: 'complete' as const, reason: 'stop' as const }
          : { type: 'incomplete' as const, reason: event.eventType === 'attempt_cancelled' ? 'cancelled' as const : event.eventType === 'attempt_failed' ? 'error' as const : 'other' as const }
        ;(message as unknown as { status?: ThreadMessageLike['status'] }).status = status
        const custom = ((message.metadata as { custom?: Record<string, unknown> } | undefined)?.custom || {})
        const relatedTools = events.filter((candidate) => candidate.attemptId === key && candidate.eventType.startsWith('tool_')).length
        ;(message as unknown as { metadata?: unknown }).metadata = {
          custom: {
            ...custom,
            resultRefs: stringRefs(event.payload.result_refs),
            evidenceRefs: stringRefs(event.payload.evidence_refs),
            admission: event.payload.admission,
            toolCount: relatedTools,
            modelContextId: event.modelContextId || (key ? contextByAttempt.get(key)?.modelContextId : undefined),
            selectionRevision: event.selectionRevision || (key ? contextByAttempt.get(key)?.selectionRevision : undefined),
            instruction: instruction?.text,
            instructionMessageId: instruction?.messageId,
            terminalPhase: event.eventType.replace(/^attempt_/, ''),
            ...(event.eventType !== 'attempt_completed' ? { terminalNotice: terminalAnswer, partialText } : {}),
            errorCode: typeof event.payload.error_code === 'string' ? event.payload.error_code : undefined,
            startedAt: custom.startedAt || (key ? startedAtByAttempt.get(key) : undefined),
            finishedAt: event.occurredAt,
            durationMs: durationBetween(typeof custom.startedAt === 'string' ? custom.startedAt : key ? startedAtByAttempt.get(key) : undefined, event.occurredAt),
          },
        }
      }
    }
  }
  for (const event of events) {
    if (!['attempt_failed', 'attempt_cancelled', 'attempt_interrupted'].includes(event.eventType)) continue
    const key = event.attemptId || event.turnId
    if (!key || assistantByAttempt.has(key)) continue
    const label = event.eventType === 'attempt_failed' ? '失败' : event.eventType === 'attempt_cancelled' ? '已取消' : '已中断'
    const message = {
      id: `assistant-${key}`,
      role: 'assistant' as const,
      content: `本次 Attempt ${label}。可以查看运行过程，并在确认模型上下文后重新运行。`,
      status: { type: 'incomplete' as const, reason: event.eventType === 'attempt_failed' ? 'error' as const : event.eventType === 'attempt_cancelled' ? 'cancelled' as const : 'other' as const },
      metadata: { custom: { attemptId: key, source: 'capstone-harness', toolCount: events.filter((candidate) => candidate.attemptId === key && candidate.eventType.startsWith('tool_')).length, instruction: instructionByAttempt.get(key)?.text, modelContextId: event.modelContextId || contextByAttempt.get(key)?.modelContextId, selectionRevision: event.selectionRevision || contextByAttempt.get(key)?.selectionRevision, terminalPhase: event.eventType.replace(/^attempt_/, ''), startedAt: startedAtByAttempt.get(key), finishedAt: event.occurredAt, durationMs: durationBetween(startedAtByAttempt.get(key), event.occurredAt) } },
    }
    messages.push(message)
    assistantByAttempt.set(key, message)
  }
  return messages.map((message) => {
    if (message.role !== 'assistant') return message
    const custom = ((message.metadata as { custom?: Record<string, unknown> } | undefined)?.custom || {})
    const attemptId = typeof custom.attemptId === 'string' ? custom.attemptId : undefined
    const activities = attemptId ? projectAssistantActivity(events.filter((candidate) => candidate.attemptId === attemptId)) : []
    const withMetadata = { ...message, metadata: { custom: { ...custom, activities } } }
    return typeof message.content === 'string'
      ? { ...withMetadata, content: [{ type: 'text' as const, text: message.content }] }
      : withMetadata
  })
}

function messageText(message: { content: unknown }): string {
  if (typeof message.content === 'string') return message.content
  if (!Array.isArray(message.content)) return ''
  return message.content.map((part) => {
    if (part && typeof part === 'object' && 'text' in part && typeof part.text === 'string') return part.text
    return ''
  }).join('')
}

function MarkdownMessage({ children }: { children?: ReactNode }) {
  return <div className="capstone-chat-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ table: ({ children }) => <div className="capstone-chat-table-scroll"><table>{children}</table></div> }}>{typeof children === 'string' ? children : String(children ?? '')}</ReactMarkdown></div>
}

async function copyToClipboard(value: string): Promise<boolean> {
  if (!value) return false
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return true
  }
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  return copied
}

function IconAction({ label, description, evidenceState, onClick, disabled = false, expanded, pressed, children }: { label: string; description?: string; evidenceState?: AnswerEvidenceState; onClick?: () => void; disabled?: boolean; expanded?: boolean; pressed?: boolean; children: ReactNode }) {
  return <button type="button" className="capstone-chat-action" aria-label={label} title={description || (disabled ? `${label}（当前不可用）` : label)} data-evidence-state={evidenceState} disabled={disabled} onClick={onClick} {...(expanded === undefined ? {} : { 'aria-expanded': expanded })} {...(pressed === undefined ? {} : { 'aria-pressed': pressed })}>{children}</button>
}

function MoreAnswerActions() {
  const [open, setOpen] = useState(false)
  const [below, setBelow] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return undefined
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      root.current?.querySelector<HTMLButtonElement>('.capstone-chat-action')?.focus()
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])
  const toggle = () => {
    const top = root.current?.getBoundingClientRect().top ?? 0
    const boundary = root.current?.closest('.capstone-chat-viewport')?.getBoundingClientRect().top ?? 0
    setBelow(top - boundary < 84)
    setOpen((value) => !value)
  }
  return <div ref={root} className="capstone-chat-more" onBlur={(event) => {
    if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    <IconAction label="更多回答操作" expanded={open} onClick={toggle}><MoreHorizontal /></IconAction>
    {open && <div className={`capstone-chat-more-panel${below ? ' opens-below' : ''}`} role="group" aria-label="更多回答操作">
      <button type="button" disabled title="反馈功能暂未启用"><ThumbsUp /><span>回答有帮助</span><small>暂未启用</small></button>
      <button type="button" disabled title="反馈功能暂未启用"><ThumbsDown /><span>回答需改进</span><small>暂未启用</small></button>
    </div>}
  </div>
}

function ChatActions({ networkSelected, onShowNetwork, role, text, evidenceRefs, evidenceState = 'not_applicable', contextId, selectionRevision, toolCount, resultAvailable, resultOpen, onShowResult, onRegenerate, onShowActivity, onEditInstruction, activityOpen, showActivity }: { networkSelected?: boolean; onShowNetwork?: () => void; role: string; text: string; evidenceRefs: string[]; evidenceState?: AnswerEvidenceState; contextId?: string; selectionRevision?: string; toolCount: number; resultAvailable?: boolean; resultOpen?: boolean; onShowResult?: () => void; onRegenerate?: () => Promise<void>; onShowActivity?: () => void; onEditInstruction?: (text: string) => void; activityOpen?: boolean; showActivity?: boolean }) {
  const [copied, setCopied] = useState(false)
  const [showEvidence, setShowEvidence] = useState(false)
  const copy = async () => {
    if (await copyToClipboard(text)) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    }
  }
  if (role === 'user') {
    return <div className="capstone-chat-actions" aria-label="消息操作"><IconAction label="编辑指令" onClick={() => onEditInstruction?.(text)}><Pencil /></IconAction><IconAction label={copied ? '已复制' : '复制指令'} onClick={() => void copy()}>{copied ? <Check /> : <Copy />}</IconAction></div>
  }
  return <>
  <div className="capstone-chat-actions" aria-label="回答操作">
    <IconAction label={copied ? '已复制' : '复制回答'} onClick={() => void copy()}>{copied ? <Check /> : <Copy />}</IconAction>
    <IconAction label="查看此指令电网图" disabled={!onShowNetwork} pressed={networkSelected} onClick={onShowNetwork}><Network /></IconAction>
    <IconAction label="查看分析结果" disabled={!resultAvailable || !onShowResult} expanded={resultOpen} onClick={onShowResult}><Activity /></IconAction>
    <IconAction label="查看证据" description={evidenceStateCopy[evidenceState]} evidenceState={evidenceState} disabled={evidenceState !== 'available'} expanded={evidenceState === 'available' && showEvidence} onClick={() => setShowEvidence((value) => !value)}><FileCheck2 /></IconAction>
    <IconAction label="查看运行过程" disabled={showActivity === false || toolCount === 0 || !onShowActivity} expanded={activityOpen} onClick={onShowActivity}><ListTree /></IconAction>
    <IconAction label="重试本次指令" disabled={!onRegenerate} onClick={() => void onRegenerate?.()}><RotateCcw /></IconAction>
    <MoreAnswerActions />
  </div>
  {evidenceState === 'available' && showEvidence && <div className="capstone-chat-evidence" role="region" aria-label="当前运行证据"><strong><FileCheck2 /> 当前运行证据</strong>{contextId && <small>模型上下文 {contextId}{selectionRevision ? ` · selection ${selectionRevision}` : ''}</small>}<div>{evidenceRefs.map((ref) => <code key={ref}>{ref}</code>)}</div></div>}
  </>
}

function RunDuration({ startedAt, durationMs, running }: { startedAt?: string; durationMs?: number; running: boolean }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  const liveDuration = startedAt ? durationBetween(startedAt, new Date(now).toISOString()) : undefined
  const elapsed = running ? liveDuration : durationMs
  if (elapsed === undefined) return null
  return <span className={`capstone-chat-duration${running ? ' is-running' : ''}`} aria-live="polite">{running ? '运行中' : '运行'} {formatDuration(elapsed)}</span>
}

function AttemptActivity({ activities, running, phase, open, startedAt, durationMs, detailsRef }: { activities: ChatActivity[]; running: boolean; phase?: string; open: boolean; startedAt?: string; durationMs?: number; detailsRef: React.RefObject<HTMLDetailsElement | null> }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  const liveDuration = startedAt ? durationBetween(startedAt, new Date(now).toISOString()) : undefined
  const elapsed = running ? liveDuration : durationMs
  if (activities.length === 0) return null
  const terminalLabel = phase === 'failed' ? '执行失败 ·' : phase === 'cancelled' ? '已取消 ·' : phase === 'interrupted' ? '已中断 ·' : '已完成'
  const terminalClass = phase === 'failed' || phase === 'interrupted' ? ` is-${phase}` : phase === 'cancelled' ? ' is-cancelled' : ''
  return <details ref={detailsRef} className={`capstone-chat-activity capstone-chat-activity-attached${terminalClass}`} open={open}>
    <summary><Activity aria-hidden="true" /><span>{running ? '正在执行' : terminalLabel} {activities.length} 个步骤{elapsed === undefined ? '' : ` · ${running ? '运行中' : '运行'} ${formatDuration(elapsed)}`}</span><small>查看运行过程</small></summary>
    <div className="capstone-chat-activity-list">{activities.map((item) => <div key={item.id} className={`capstone-chat-activity-item is-${item.status}`}><span className="capstone-chat-activity-icon" aria-hidden="true" /> <span><strong>{item.label}</strong><small>{item.source}{item.durationMs === undefined ? '' : ` · ${formatDuration(item.durationMs)}`}</small></span></div>)}</div>
  </details>
}

function admissionAccepted(admission: unknown): boolean {
  return Boolean(admission && typeof admission === 'object' && (
    (typeof (admission as { status?: unknown }).status === 'string'
      && (admission as { status?: unknown }).status === 'admitted')
    || (typeof (admission as { mode?: unknown }).mode === 'string'
      && typeof (admission as { assurance?: unknown }).assurance === 'string')
  ))
}

function RunArtifacts({ resultRefs, evidenceRefs, admission }: { resultRefs: string[]; evidenceRefs: string[]; admission: unknown }) {
  // Structured results are opened from the compact action bar.  Keep this
  // surface for admission state only; raw result hashes are deliberately not
  // repeated below every assistant answer.
  if (resultRefs.length === 0 && evidenceRefs.length === 0) return null
  const admitted = admissionAccepted(admission)
  if (!admitted) return null
  const admissionRef = admission && typeof admission === 'object' && 'admission_ref' in admission && typeof (admission as { admission_ref?: unknown }).admission_ref === 'string'
    ? (admission as { admission_ref: string }).admission_ref : undefined
  return <div className="capstone-chat-artifacts" aria-label="当前运行结果引用">
    {resultRefs.length > 0 && <div className="capstone-chat-reference-status" role="status"><Activity aria-hidden="true" /><span>{resultRefs.length} 项结构化结果{admitted ? '已准入' : '已记录'}</span>{admissionRef && <small>准入已记录</small>}</div>}
    {/* Evidence is intentionally opened from the answer action bar. Keeping the
        long evidence identifier out of the default answer preserves the compact
        assistant-ui reading flow while retaining the current-run admission gate. */}
  </div>
}

function resultCell(value: string | number | boolean | null): string {
  if (value === null) return '—'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  return String(value)
}

function ResultProjectionCard({ projection, onFocusElement }: { projection: ResultProjection; onFocusElement?: (projection: ResultProjection, elementId: string) => void }) {
  const statusLabel = projection.status === 'completed' ? '已完成' : projection.status === 'partial' ? '部分结果' : '暂不可用'
  return <section className={`capstone-result-card is-${projection.status}`} aria-label="结构化分析结果">
    <div className="capstone-result-heading"><div><Activity aria-hidden="true" /><strong>分析结果</strong><span>{statusLabel}</span></div><small>{projection.source.capabilityId}</small></div>
    {projection.unavailableReason && <p className="capstone-result-reason">{projection.unavailableReason}</p>}
    {projection.summary.length > 0 && <div className="capstone-result-metrics">{projection.summary.map((metric) => <div key={metric.metricId}><span>{metric.label}</span><strong>{resultCell(metric.value)}{metric.unit ? ` ${metric.unit}` : ''}</strong></div>)}</div>}
    {projection.tables.map((table) => <div className="capstone-result-table-wrap" key={table.tableId}><div className="capstone-result-table-title">{table.title}</div><div className="capstone-result-table-scroll"><table><thead><tr>{table.columns.map((column) => <th key={column.columnId}>{column.label}{column.unit ? ` (${column.unit})` : ''}</th>)}</tr></thead><tbody>{table.rows.map((row) => <tr key={row.rowId}>{table.columns.map((column) => <td key={column.columnId}>{row.elementRef && column === table.columns[0] ? <button type="button" className="capstone-result-element" onClick={() => onFocusElement?.(projection, row.elementRef!.elementId)} title="在左侧拓扑图中定位">{resultCell(row.cells[column.columnId] ?? row.rowId)}</button> : resultCell(row.cells[column.columnId] ?? null)}</td>)}</tr>)}</tbody></table></div></div>)}
  </section>
}

function FoldableAnswer({ id, text }: { id: string; text: string }) {
  const body = useRef<HTMLDivElement>(null)
  const { collapsed, toggle } = useContext(AnswerReadingContext)
  // The zero-layout fallback is used by server/test rendering. Browsers use the
  // actual Markdown height, including tables, headings and wrapped short text.
  const [foldable, setFoldable] = useState(text.length > 220 || text.split('\n').length > 3)
  const [previewHeight, setPreviewHeight] = useState(51.15)
  useLayoutEffect(() => {
    const node = body.current
    if (!node) return
    const measure = () => {
      if (node.scrollHeight === 0) return
      const lineHeight = Number.parseFloat(getComputedStyle(node).lineHeight) || 17.05
      const height = lineHeight * 3
      setPreviewHeight(height)
      setFoldable(node.scrollHeight > height + 1)
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(node)
    window.addEventListener('resize', measure)
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure) }
  }, [text])
  const folded = foldable && collapsed.has(id)
  return <div className={`capstone-answer${folded ? ' is-collapsed' : ''}`} data-answer-state={folded ? 'collapsed' : 'expanded'}>
    {foldable && !folded && <button type="button" className="capstone-answer-toggle is-top" aria-label="折叠回答" title="收起并定位到用户指令" aria-expanded={true} aria-controls={`${id}-content`} onClick={() => toggle(id)}><ChevronUp aria-hidden="true" /><span>收起</span></button>}
    <div ref={body} id={`${id}-content`} className={`capstone-answer-content${folded ? ' is-collapsed' : ''}`} style={folded ? { maxHeight: previewHeight } : undefined} aria-hidden={folded || undefined} inert={folded || undefined}>
      <MarkdownMessage>{text}</MarkdownMessage>
    </div>
    {folded && <span className="visually-hidden">{text.slice(0, 220)}…</span>}
    {foldable && <button type="button" className={`capstone-answer-toggle${folded ? ' is-collapsed' : ' is-bottom'}`} aria-label={folded ? '展开完整回答' : '折叠回答并返回指令'} title={folded ? '展开并定位到用户指令' : '收起并定位到用户指令'} aria-expanded={!folded} aria-controls={`${id}-content`} onClick={() => toggle(id)}>{folded ? <><ChevronRight aria-hidden="true" /><span className="capstone-answer-state">已折叠</span><span>展开</span></> : <><ChevronUp aria-hidden="true" /><span>收起</span></>}</button>}
  </div>
}

function HistoryAnswerActions({ disabled, onFold, onUnfold }: { disabled: boolean; onFold: () => void; onUnfold: () => void }) {
  const close = useCloseThreadSettings()
  return <div className="thread-history-actions" role="group" aria-label="历史回答整理">
    <span className="thread-settings-section">历史回答</span>
    <button type="button" className="thread-settings-item" disabled={disabled} onClick={() => { onFold(); close() }}>折叠历史回答</button>
    <button type="button" className="thread-settings-item" disabled={disabled} onClick={() => { onUnfold(); close() }}>展开历史回答</button>
    <small>仅已加载回答 · 新回答完整显示</small>
  </div>
}

function ChatMessage({ selectedNetworkAttempt, networkAttemptIds = [], onShowNetwork, onRegenerate, canRerunCompleted, onEditInstruction, modelSummary, showActivity = true, resultProjections, onFocusElement }: { selectedNetworkAttempt?: string; networkAttemptIds?: readonly string[]; onShowNetwork?: (attemptId: string) => void; onRegenerate?: (attemptId: string, instruction?: string) => Promise<void>; canRerunCompleted: boolean; onEditInstruction?: (text: string) => void; modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string }; showActivity?: boolean; resultProjections?: readonly ResultProjection[]; onFocusElement?: (projection: ResultProjection, elementId: string) => void }) {
  const activityRef = useRef<HTMLDetailsElement>(null)
  const role = useAuiState((state) => state.message.role)
  const content = useAuiState((state) => state.message.content)
  const id = useAuiState((state) => state.message.id)
  const { restoreAnchor } = useContext(AnswerReadingContext)
  useLayoutEffect(() => restoreAnchor(id), [id, restoreAnchor])
  const status = useAuiState((state) => state.message.status)
  const custom = useAuiState((state) => state.message.metadata?.custom) as Record<string, unknown> | undefined
  const hasText = messageText({ content }).trim().length > 0
  const text = messageText({ content })
  const attemptId = id.replace(/^assistant-/, '')
  const attemptResultProjections = resultProjections?.filter((item) => item.attemptId === attemptId) ?? []
  const evidenceRefs = stringRefs(custom?.evidenceRefs)
  const resultRefs = stringRefs(custom?.resultRefs)
  const admission = custom?.admission
  const evidenceState = answerEvidenceState(
    typeof custom?.terminalPhase === 'string' ? custom.terminalPhase : status?.type === 'running' ? 'running' : undefined,
    admission, evidenceRefs, typeof custom?.errorCode === 'string' ? custom.errorCode : undefined,
  )
  const instruction = typeof custom?.instruction === 'string' ? custom.instruction : undefined
  const startedAt = typeof custom?.startedAt === 'string' ? custom.startedAt : undefined
  const durationMs = typeof custom?.durationMs === 'number' ? custom.durationMs : undefined
  const toolCount = typeof custom?.toolCount === 'number' ? custom.toolCount : 0
  const contextId = typeof custom?.modelContextId === 'string' ? custom.modelContextId : undefined
  const selectionRevision = typeof custom?.selectionRevision === 'string' ? custom.selectionRevision : undefined
  const answerModel = contextId === modelSummary?.contextId ? modelSummary : undefined
  const activities = Array.isArray(custom?.activities) ? custom.activities as ChatActivity[] : []
  const [activityOpen, setActivityOpen] = useState(status?.type === 'running')
  const [resultOpen, setResultOpen] = useState(false)
  useEffect(() => {
    if (status?.type !== 'running') setActivityOpen(false)
  }, [status?.type])
  const terminalWithoutText = role === 'assistant' && !hasText && status?.type !== 'running'
  const toggleActivity = () => {
    setActivityOpen((value) => {
      const next = !value
      if (activityRef.current) activityRef.current.open = next
      return next
    })
  }
  const messageState = status?.type === 'running' ? 'running' : typeof custom?.terminalPhase === 'string' ? custom.terminalPhase : status?.type
  const retryable = ['failed', 'cancelled', 'interrupted'].includes(String(custom?.terminalPhase)) ||
    (custom?.terminalPhase === 'completed' && canRerunCompleted && instruction?.trim() &&
      (!modelSummary || contextId === modelSummary.contextId))
  const notice = custom?.systemNotice as SystemNotice | undefined
  const onSystemAction = useContext(SystemActionContext)
  if (notice) return <MessagePrimitive.Root data-message-id={id} tabIndex={-1} aria-label="系统提示" className="capstone-chat-message is-system">
    <ThreadSystemNotice tone={notice.tone} instruction={notice.instruction} action={notice.action === 'resync' ? '重新同步' : notice.action === 'reconnect' ? '重新连接' : undefined} onAction={notice.action ? () => onSystemAction?.(notice.action!) : undefined}>{notice.text}</ThreadSystemNotice>
  </MessagePrimitive.Root>
  const terminalNotice = typeof custom?.terminalNotice === 'string' ? custom.terminalNotice : undefined
  return <MessagePrimitive.Root data-message-id={id} tabIndex={-1} aria-label={role === 'user' ? '用户指令' : '智能体回答'} className={`capstone-chat-message is-${role}${messageState ? ` is-${messageState}` : ''}`}>
    <div className="capstone-chat-body">
      <span className="capstone-chat-role">{role === 'user' ? '你' : 'CAPSTONE'}</span>
      {terminalNotice ? <>
        {typeof custom?.partialText === 'string' && custom.partialText && <MarkdownMessage>{custom.partialText}</MarkdownMessage>}
        <ThreadSystemNotice tone={custom?.terminalPhase === 'failed' ? 'error' : 'info'}><MarkdownMessage>{terminalNotice}</MarkdownMessage></ThreadSystemNotice>
      </> : hasText && role === 'assistant' && status?.type === 'complete' ? <FoldableAnswer id={id} text={text} /> : hasText
        ? <MessagePrimitive.Parts components={{ Text: role === 'assistant' ? () => <MessagePartPrimitive.Text smooth={false} render={<MarkdownMessage />} /> : () => <MessagePartPrimitive.Text smooth={false} component="p" /> }} />
        : role === 'assistant' && <span className={`capstone-chat-placeholder${terminalWithoutText ? ' is-terminal' : ''}`}>{terminalWithoutText ? 'Attempt 已结束，暂无可显示的回答。' : '正在生成回答…'}</span>}
    </div>
    {role === 'assistant' && <div className="capstone-chat-footer">
      <RunDuration startedAt={startedAt} durationMs={durationMs} running={status?.type === 'running'} />
      {(hasText || terminalWithoutText) && <ChatActions networkSelected={selectedNetworkAttempt === attemptId} onShowNetwork={networkAttemptIds.includes(attemptId) && onShowNetwork ? () => onShowNetwork(attemptId) : undefined} role={role} text={text} evidenceRefs={evidenceState === 'available' ? evidenceRefs : []} evidenceState={evidenceState} resultAvailable={attemptResultProjections.length > 0} resultOpen={resultOpen} onShowResult={() => setResultOpen((value) => !value)} contextId={contextId} selectionRevision={selectionRevision} toolCount={activities.length || toolCount} activityOpen={activityOpen} showActivity={showActivity} onShowActivity={toggleActivity} onRegenerate={retryable && onRegenerate ? () => onRegenerate(attemptId, instruction) : undefined} />}
    </div>}
    {role === 'assistant' && attemptResultProjections.length > 0 && resultOpen && <div className="capstone-result-group">{attemptResultProjections.map((projection) => <ResultProjectionCard key={projection.resultId} projection={projection} onFocusElement={onFocusElement} />)}</div>}
    {role === 'assistant' && <RunArtifacts resultRefs={resultRefs} evidenceRefs={evidenceRefs} admission={admission} />}
    {role === 'user' && hasText && <ChatActions role={role} text={text} evidenceRefs={[]} toolCount={0} onEditInstruction={onEditInstruction} />}
    {role === 'assistant' && (showActivity || status?.type === 'running') && <AttemptActivity activities={activities} phase={typeof custom?.terminalPhase === 'string' ? custom.terminalPhase : undefined} running={status?.type === 'running'} open={status?.type === 'running' || activityOpen} startedAt={startedAt} durationMs={durationMs} detailsRef={activityRef} />}
  </MessagePrimitive.Root>
}

function ComposerSurface({ disabled, isRunning, editRequest, acceptedDraft, controls, storageKey }: { disabled: boolean; isRunning: boolean; editRequest?: { text: string; nonce: number }; acceptedDraft?: { text: string; commandId: string }; controls?: ReactNode; storageKey?: string }) {
  const aui = useAui()
  const isEmpty = useAuiState((state) => state.composer.isEmpty)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const resolvedCommand = useRef<string | undefined>(undefined)
  const text = useAuiState((state) => state.composer.text)
  useEffect(() => {
    writeDraft(storageKey, text)
  }, [text, storageKey])
  useEffect(() => {
    if (editRequest) aui.composer.setText(editRequest.text)
  }, [aui, editRequest])
  useEffect(() => {
    if (acceptedDraft && resolvedCommand.current !== acceptedDraft.commandId) {
      resolvedCommand.current = acceptedDraft.commandId
      if (aui.composer.getState().text.trim() === acceptedDraft.text.trim()) aui.composer.setText('')
    }
  }, [aui, acceptedDraft])
  useEffect(() => {
    const input = inputRef.current
    if (input && !input.disabled) input.focus()
  }, [disabled, isRunning])
  return <ComposerPrimitive.Root className="capstone-composer-root" data-running={isRunning ? 'true' : 'false'} data-empty={isEmpty ? 'true' : 'false'}>
    <ComposerPrimitive.Input ref={inputRef} autoFocus aria-label="Thread 指令" placeholder={isRunning ? '可先写下一条指令，完成后发送…' : disabled ? '当前状态暂不可提交新指令' : '围绕当前电网模型输入指令…'} disabled={disabled && !isRunning} submitMode="enter" />
    <div className="capstone-composer-footer"><div className="capstone-composer-toolbar" aria-label="输入工具栏">{controls}</div><div className="capstone-composer-actions">
      {isRunning ? <ComposerPrimitive.Cancel className="capstone-chat-stop" aria-label="停止生成" title="停止生成" onMouseDown={(event) => event.preventDefault()}><Square aria-hidden="true" /></ComposerPrimitive.Cancel> : <ComposerPrimitive.Send className="capstone-chat-send" aria-label="发送指令" title="发送指令" disabled={disabled || isEmpty} onMouseDown={(event) => event.preventDefault()}><ArrowUp aria-hidden="true" /></ComposerPrimitive.Send>}
    </div></div>
  </ComposerPrimitive.Root>
}

function EmptyThreadState({ disabled }: { disabled: boolean }) {
  const aui = useAui()
  return <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><div className="capstone-chat-suggestions" aria-label="示例问题">
    {EMPTY_PROMPTS.map((prompt) => <button key={prompt} type="button" className="capstone-chat-suggestion" disabled={disabled} onClick={() => { aui.composer.setText(prompt); aui.composer.send() }}>{prompt}</button>)}
  </div></div>
}

export type CapstoneAssistantThreadProps = {
  systemNotices?: readonly SystemNotice[]
  onSystemAction?: (action: 'reconnect' | 'resync') => void
  storageKey?: string
  hasOlderHistory?: boolean
  historyLoading?: boolean
  onLoadOlder?: () => Promise<void>
  historyAtLatest?: boolean
  onReturnLatest?: () => void
  events: readonly EventEnvelope[]
  disabled: boolean
  isRunning: boolean
  acceptedDraft?: { text: string; commandId: string }
  activity: readonly (ChatActivity | string)[]
  onSend: (mode: SendMode, text: string) => Promise<void>
  onCancel: () => Promise<void>
  onRegenerate?: (attemptId: string, instruction?: string) => Promise<void>
  canRerunCompleted?: boolean
  modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string }
  composerControls?: (historyActions: ReactNode) => ReactNode
  showActivity?: boolean
  caseExecution?: CaseExecutionSnapshot | null
  caseCatalog?: readonly ThreadCatalogCase[]
  caseConnection?: ThreadTransportState | 'connecting'
  onCaseAction?: (actionId: CaseActionSnapshot['actionId']) => void
  onCaseStart?: (caseId: string, caseVersion: string) => void
  resultProjections?: readonly ResultProjection[]
  onFocusElement?: (projection: ResultProjection, elementId: string) => void
  networkAttemptIds?: readonly string[]
  selectedNetworkAttempt?: string
  onShowNetwork?: (attemptId: string) => void
}

/** Assistant-ui is the presentation runtime; Capstone projection remains authoritative. */
const SystemActionContext = createContext<CapstoneAssistantThreadProps['onSystemAction']>(undefined)

export default function CapstoneAssistantThread({ events, systemNotices = [], onSystemAction, disabled, isRunning, acceptedDraft, activity, onSend, onCancel, onRegenerate, canRerunCompleted = !disabled, modelSummary, composerControls, showActivity = true, caseExecution, caseCatalog = [], caseConnection = 'live', onCaseAction, onCaseStart, resultProjections = [], onFocusElement, selectedNetworkAttempt, networkAttemptIds = [], onShowNetwork, storageKey, hasOlderHistory = false, historyLoading = false, onLoadOlder, historyAtLatest = true, onReturnLatest }: CapstoneAssistantThreadProps) {
  const allMessages = useMemo(() => projectSystemNotices(projectAssistantMessages(events), events, systemNotices, historyAtLatest), [events, systemNotices, historyAtLatest])
  const [foldState, setFoldState] = useState<{ thread: string | undefined; ids: ReadonlySet<string> }>({ thread: storageKey, ids: new Set() })
  const collapsedAnswers = foldState.thread === storageKey ? foldState.ids : new Set<string>()
  const viewportRef = useRef<HTMLDivElement>(null)
  const [readingLayoutChanging, setReadingLayoutChanging] = useState(false)
  const scrollAnchor = useRef<{ id: string; top: number; focus: boolean } | null>(null)
  function captureScrollAnchor(answerId?: string) {
    const viewport = viewportRef.current
    if (!viewport) return
    const top = viewport.getBoundingClientRect().top
    const nodes = Array.from(viewport.querySelectorAll<HTMLElement>('[data-message-id]'))
    const visible = nodes.find((item) => item.getBoundingClientRect().bottom > top)
    const messageId = answerId || visible?.dataset.messageId
    const message = allMessages.find((item) => item.id === messageId)
    const instructionId = message?.metadata?.custom?.instructionMessageId
    const id = typeof instructionId === 'string' ? instructionId : messageId
    const instructionIndex = allMessages.findIndex((item) => item.id === id)
    if (!id || instructionIndex < 0) return
    setReadingLayoutChanging(true)
    const isInstruction = allMessages[instructionIndex]?.role === 'user'
    const node = nodes.find((item) => item.dataset.messageId === id)
    scrollAnchor.current = { id, top: isInstruction || answerId ? top + 12 : Math.max(top, node?.getBoundingClientRect().top || top), focus: isInstruction || Boolean(answerId) }
    if (!node) {
      // The first answer in the 50-message window can have its instruction just
      // outside it. Show the loaded instruction and its answer together.
      setWindowAnchor(allMessages[Math.min(allMessages.length - 1, instructionIndex + 49)]?.id || null)
    }
  }
  function restoreReadingAnchor(id?: string) {
    const anchor = scrollAnchor.current
    if (!anchor || (id && anchor.id !== id)) return
    const viewport = viewportRef.current
    const node = anchor && Array.from(viewport?.querySelectorAll<HTMLElement>('[data-message-id]') || []).find((item) => item.dataset.messageId === anchor.id)
    if (anchor && node && viewport) {
      scrollAnchor.current = null
      viewport.scrollTop += node.getBoundingClientRect().top - anchor.top
      if (anchor.focus) node.focus({ preventScroll: true })
    }
  }
  useLayoutEffect(() => restoreReadingAnchor(), [foldState])
  useEffect(() => {
    if (!readingLayoutChanging) return
    // Assistant-ui follows height changes while at the latest reply. Pause that
    // behavior until the chosen instruction anchor and content resize settle.
    let second: number | undefined
    const first = window.requestAnimationFrame(() => {
      second = window.requestAnimationFrame(() => setReadingLayoutChanging(false))
    })
    return () => { window.cancelAnimationFrame(first); if (second !== undefined) window.cancelAnimationFrame(second) }
  }, [readingLayoutChanging, foldState])
  useEffect(() => {
    setFoldState((state) => state.thread === storageKey ? state : { thread: storageKey, ids: new Set() })
  }, [storageKey])
  function toggleAnswer(id: string) {
    captureScrollAnchor(id)
    setFoldState((state) => {
      const ids = new Set(state.thread === storageKey ? state.ids : [])
      if (ids.has(id)) ids.delete(id); else ids.add(id)
      return { thread: storageKey, ids }
    })
  }
  const completedAnswers = allMessages.filter((message) => message.role === 'assistant' && message.status?.type === 'complete' && !message.metadata?.custom?.systemNotice)
  function organizeHistory(fold: boolean) {
    captureScrollAnchor()
    const snapshot = completedAnswers.flatMap((message) => message.id ? [message.id] : [])
    setFoldState((state) => {
      const ids = new Set(state.thread === storageKey ? state.ids : [])
      for (const id of snapshot) { if (fold) ids.add(id); else ids.delete(id) }
      return { thread: storageKey, ids }
    })
  }
  const [windowAnchor, setWindowAnchor] = useState<string | null>(null)
  const anchoredIndex = windowAnchor === null ? -1 : allMessages.findIndex((message) => message.id === windowAnchor)
  const windowEnd = anchoredIndex < 0 ? allMessages.length : anchoredIndex + 1
  const windowStart = Math.max(0, windowEnd - 50)
  const messages = allMessages.slice(windowStart, windowEnd)
  const [historyError, setHistoryError] = useState<string | null>(null)
  async function olderMessages() {
    setHistoryError(null)
    if (windowStart > 0) {
      setWindowAnchor(allMessages[Math.max(0, windowStart + 24)]?.id || null)
      return
    }
    if (!onLoadOlder || historyLoading) return
    const anchor = allMessages[Math.min(24, windowEnd - 1)]?.id
    try {
      await onLoadOlder()
      if (anchor) setWindowAnchor(anchor)
    } catch (cause) { setHistoryError(cause instanceof Error ? cause.message : '更早消息暂不可用') }
  }
  const [initialDraft] = useState(() => readDraft(storageKey))
  const [editRequest, setEditRequest] = useState<{ text: string; nonce: number }>()
  const normalizedActivity = activity.map((item) => typeof item === 'string' ? { id: item, label: item, source: 'capstone-harness', status: 'completed' as const } : item)
  const legacyActivity = activity.some((item) => typeof item === 'string')
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    convertMessage: (message) => message,
    isSendDisabled: disabled,
    isRunning,
    onNew: async (message) => {
      const text = messageText(message)
      if (text.trim()) {
        await onSend('automatic', text.trim()); setWindowAnchor(null)
        if (!historyAtLatest) onReturnLatest?.()
      }
    },
    onEdit: async (message) => {
      const text = messageText(message)
      if (text.trim()) await onSend('automatic', text.trim())
    },
    onCancel,
  })
  useEffect(() => {
    if (initialDraft) runtime.thread.composer.setText(initialDraft)
  }, [runtime, initialDraft])

  return <AssistantRuntimeProvider runtime={runtime}>
    <SystemActionContext.Provider value={onSystemAction}>
    <AnswerReadingContext.Provider value={{ collapsed: collapsedAnswers, toggle: toggleAnswer, restoreAnchor: restoreReadingAnchor }}>
    <ChatMessageContext.Provider value={{ selectedNetworkAttempt, networkAttemptIds, onShowNetwork, onRegenerate: isRunning ? undefined : onRegenerate, canRerunCompleted, onEditInstruction: (text) => setEditRequest({ text, nonce: Date.now() }), modelSummary, showActivity, resultProjections, onFocusElement }}>
    <div className="capstone-assistant-thread" data-testid="assistant-ui-chat">
      <div className="capstone-assistant-runtime-label"><span className="assistant-live-dot" />CAPSTONE <span>· HARNESS</span><small>实时响应</small></div>
      <ThreadPrimitive.Root className="capstone-chat-runtime">
        {(hasOlderHistory || windowStart > 0 || windowAnchor !== null || !historyAtLatest || historyError) && <div className="capstone-chat-history-controls" aria-label="消息历史">
          {(hasOlderHistory || windowStart > 0) && <button type="button" disabled={historyLoading} onClick={() => void olderMessages()}>{historyLoading ? '正在加载…' : '查看之前的对话'}</button>}
          {(windowAnchor !== null || !historyAtLatest) && <button type="button" onClick={() => { setWindowAnchor(null); if (!historyAtLatest) onReturnLatest?.() }}>返回最新对话</button>}
          {historyError && <span role="alert">{historyError}</span>}
        </div>}
        {!caseExecution && caseCatalog.length > 0 && <ThreadCasePicker cases={caseCatalog} disabled={disabled || caseConnection === 'resync_required'} onStart={(caseId, caseVersion) => onCaseStart?.(caseId, caseVersion)} />}
        {caseExecution && <ThreadCaseProgress execution={caseExecution} connection={caseConnection} onAction={(actionId) => onCaseAction?.(actionId)} />}
        {typeof ResizeObserver === 'undefined' ? <div ref={viewportRef} className="capstone-chat-viewport">
          {messages.length === 0 && <EmptyThreadState disabled={disabled} />}
          <ThreadPrimitive.Messages components={{ Message: ThreadChatMessage }} />
        </div> : <ThreadPrimitive.Viewport ref={viewportRef} className="capstone-chat-viewport" autoScroll={!readingLayoutChanging} scrollToBottomOnInitialize={false}>
          {messages.length === 0 && <EmptyThreadState disabled={disabled} />}
          <ThreadPrimitive.Messages components={{ Message: ThreadChatMessage }} />
        </ThreadPrimitive.Viewport>}
        {legacyActivity && normalizedActivity.length > 0 && <details className="capstone-chat-activity" open={isRunning}>
          <summary><Activity aria-hidden="true" /><span>{isRunning ? '正在执行' : '已完成'} {normalizedActivity.length} 个步骤</span><small>查看运行过程</small></summary>
          <div className="capstone-chat-activity-list">{normalizedActivity.slice(-5).map((item) => <div key={item.id} className={`capstone-chat-activity-item is-${item.status}`}><span className="capstone-chat-activity-icon" aria-hidden="true" /> <span><strong>{item.label}</strong><small>{item.source}</small></span></div>)}</div>
        </details>}
        <div className="capstone-chat-composer">
          <ComposerSurface disabled={disabled} isRunning={isRunning} editRequest={editRequest} acceptedDraft={acceptedDraft} controls={composerControls ? composerControls(<HistoryAnswerActions disabled={completedAnswers.length === 0} onFold={() => organizeHistory(true)} onUnfold={() => organizeHistory(false)} />) : <ThreadSettingsMenu><HistoryAnswerActions disabled={completedAnswers.length === 0} onFold={() => organizeHistory(true)} onUnfold={() => organizeHistory(false)} /></ThreadSettingsMenu>} storageKey={storageKey} />
        </div>
      </ThreadPrimitive.Root>
    </div>
    </ChatMessageContext.Provider>
    </AnswerReadingContext.Provider>
    </SystemActionContext.Provider>
  </AssistantRuntimeProvider>
}
