import ResearchProgressSummary from './ResearchProgressSummary'
import {applicationCapacity,observeCapacity} from './applicationCapacity'
import {capacityFailureNotice} from './capacityFailure'
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode,type RefObject } from 'react'
import {useSessionViewState,useSessionViewRef,useHasSavedSessionPosition} from './workspaceSessionCache'
import { createPortal } from 'react-dom'
import ProductReferenceChips,{type ProductReferenceReader} from './ProductReferenceChips'
import {productRefKey,parseContextProductRefs,type ContextProductRef} from './threadProducts'
import { readDraft, writeDraft } from './threadSessionState'
import ThreadCommandMenu from './ThreadCommandMenu'
import InstructionAttachments,{bindInstructionAttachments,type InstructionFile} from './InstructionAttachments'
import { buildInputSubmission, emptyInputDraft, readInputDraft, writeInputDraft, inputDraftError, type InputCatalog, type InputDraft, type InputSubmission } from './threadInput'
import ThreadSettingsMenu, { useCloseThreadSettings } from './ThreadSettingsMenu'
import ThreadSystemNotice from './ThreadSystemNotice'
import { projectSystemNotices, type ThreadSystemNotice as SystemNotice } from './threadSystemNotices'
import { answerEvidenceState, evidenceStateCopy, type AnswerEvidenceState } from './threadEvidenceState'
import InferenceEvidencePanel, { type FailureEvidence, type ToolExecutionRecord } from './InferenceEvidencePanel'
import ResearchEvidence, { parseResearchSnapshot, type ResearchSnapshot } from './ResearchEvidence'
import { projectTaskProgress, projectTaskStepDiagnostics, projectResearchBranches, type TaskProgress, type TaskStepDiagnostic, type ResearchBranch } from './taskProgress'
import TaskStepProcess, { RecordedResult, StepErrorDetails, projectTaskSteps, ResearchBranchItems, readStepOpen, saveStepOpen, toolExecutionMs, type StepFoldCommand, type TaskStep } from './TaskStepProcess'
import ExecutionGraphProcess, { graphTraceIssues, type GraphTraceFocus } from './ExecutionGraphProcess'
import ProcessCallTrace, { modelCallMs, type ProcessModelCall } from './ProcessCallTrace'
import { projectProcessModelRequests } from './processModelRequests'
import {summarizeLlmPoolCalls} from './processLlmPool'
import {isExecutionLifecycleStep} from './executionLifecycle'
import {nativeGraphFocus} from './nativeGraphFocus'
import ThinkingProcess,{projectInitialThinking,type InitialThinking} from './ThinkingProcess'
import { projectExecutionGraph, type ExecutionGraph } from './executionGraph'
import ResultExplorer from './ResultExplorer'
import { taskResultCollections, type TaskResultCollection } from './taskResultCollections'
import InstructionMarkers from './InstructionMarkers'
import AnswerDetailSheet from './AnswerDetailSheet'
import AttemptRecordPanel, { type AttemptRecordReader } from './AttemptRecordPanel'
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
import { AlertTriangle, Activity, ArrowUp, Check, ChevronDown, ChevronUp, Copy, FileCheck2, ListTree, Network, RotateCcw, Square, MessageCircle, Maximize2, ChevronsUpDown, ChevronsDownUp } from 'lucide-react'
import MarkdownContent from './MarkdownContent'
import type { EventEnvelope, ResultProjection, RuntimeMode } from './threadProtocol'
import type { CaseActionSnapshot, CaseExecutionSnapshot } from './threadProtocol'
import type { ThreadTransportState } from './threadClient'
import {projectNativeArtifacts,type NativeArtifact} from './nativeArtifacts'
import InstructionFiles from './InstructionFiles'
import type { ThreadCatalogCase } from './threadCatalog'
import { attemptFailureCopy, toolFailureCopy, toolFailureReason } from './threadFeedback'

type SendMode = 'automatic' | 'ordinary' | 'professional'

const AnswerReadingContext = createContext<{
  collapsed: ReadonlySet<string>
  toggle: (id: string, control: HTMLButtonElement) => void
  restoreAnchor: (id: string) => void
  preserveControl: (id: string, element: HTMLElement) => void
}>({ collapsed: new Set(), toggle: () => {}, restoreAnchor: () => {}, preserveControl: () => {} })

const ChatMessageContext = createContext<Parameters<typeof ChatMessage>[0] | null>(null)
const AttemptRecordsContext = createContext<AttemptRecordReader | undefined>(undefined)

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
  taskStepId?: string
  taskStepNumber?: number
  stepToolNumber?: number
  failure?: { code?: string; message?: string; summary?: string }
  operation?: string
  outputExcerpt?: string
}

const TOOL_LABELS: Record<string, string> = {
  agent_research_read: '读取已保存的研究记录',
  agent_research_update: '保存研究进展与待解决问题',
  agent_research_depth: '调整后续推理深度',
  agent_task_progress: '记录任务进展',
  agent_tools_execute: '组合工具与计算',
  agent_task_records_read: '读取原任务记录',
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
  const name = toolName(event)
  const binding = typeof event.payload.binding_id === 'string' ? event.payload.binding_id
    : name.startsWith('grid_') ? 'grid' : name.startsWith('pypsa_') ? 'pypsa' : 'capstone'
  const capability = typeof event.payload.capability === 'string' ? event.payload.capability : toolName(event)
  return `${binding} · ${capability}`
}

/** Native observations stay distinct from Authority semantic tool events. */
function nativeToolActivity(event:EventEnvelope) {
  if(event.visibility!=='public'||event.eventType!=='runtime_event'||!event.attemptId)return
  const text=(value:unknown):value is string=>typeof value==='string'&&value.length>0&&value.length<=256&&value.trim()===value&&!/[\u0000-\u001f\u007f]/.test(value)
  const object=(value:unknown)=>value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:undefined
  const payload=event.payload
  let task=payload.task_id,name=payload.tool_name,call=payload.tool_call_id
  let phase:'running'|'completed'='completed'
  let failed=payload.is_error===true
  let activity=object(payload.activity)
  if(payload.native_type==='tool_execution_start'||payload.native_type==='tool_execution_end') {
    phase=payload.native_type==='tool_execution_start'?'running':'completed'
  }else{
    const reference=object(payload.reference),metadata=object(reference?.metadata)
    if(payload.external_reference_kind!=='sources'||reference?.kind!=='native_tool_observation'
      ||reference.parent_attempt_id!==event.attemptId||(task!==undefined&&reference.task_id!==task)||!metadata)return
    task=reference.task_id;name=metadata.tool_name;call=metadata.tool_call_id;failed=metadata.is_error===true
    activity=object(metadata.activity)
  }
  if(!text(task)||!text(call)||!text(name))return
  const operation=typeof activity?.operation==='string'?activity.operation.slice(0,241):undefined
  const rawOutput=typeof activity?.output_excerpt==='string'?activity.output_excerpt:undefined
  const outputExcerpt=rawOutput&&/(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization|password|secret)["']?\s*[:=]/i.test(rawOutput)?'输出包含受保护配置或凭据信息，已隐藏。':rawOutput?.slice(0,601)
  return {id:`native:${JSON.stringify([event.threadId,event.attemptId,task,call])}`,name,phase,failed,operation,outputExcerpt}
}

export function projectAssistantActivity(events: readonly EventEnvelope[]): ChatActivity[] {
  const grouped = new Map<string, ChatActivity>()
  for (const event of events) {
    const native=nativeToolActivity(event)
    if(native){
      const previous=grouped.get(native.id)
      const startedAt=previous?.startedAt||(native.phase==='running'?event.occurredAt:undefined)
      const finishedAt=previous?.finishedAt||(native.phase==='completed'?event.occurredAt:undefined)
      grouped.set(native.id,{id:native.id,label:TOOL_LABELS[native.name] || native.name,source:`pi · ${native.name}`,
        taskStepId:typeof event.payload.task_step_id==='string'?event.payload.task_step_id:previous?.taskStepId,
        taskStepNumber:typeof event.payload.task_step_number==='number'?event.payload.task_step_number:previous?.taskStepNumber,
        stepToolNumber:typeof event.payload.step_tool_number==='number'?event.payload.step_tool_number:previous?.stepToolNumber,
        operation:native.operation||previous?.operation,outputExcerpt:native.outputExcerpt||previous?.outputExcerpt,
        ...(native.failed&&native.outputExcerpt?{failure:{summary:native.outputExcerpt}}:previous?.failure?{failure:previous.failure}:{}),
        status:native.failed||previous?.status==='failed'?'failed':finishedAt?'completed':native.phase,
        ...(startedAt?{startedAt}:{}),...(finishedAt?{finishedAt}:{}),
        ...(startedAt&&finishedAt?{durationMs:durationBetween(startedAt,finishedAt)}:{})})
      continue
    }
    if (event.eventType === 'research_step_resumed') {
      grouped.set(event.eventId, { id: event.eventId, label: '推理等待达到时限，继续当前会话',
        source: 'capstone · research', status: 'completed', finishedAt: event.occurredAt })
      continue
    }
    if (!['tool_started', 'tool_completed', 'tool_failed', 'tool_cancelled'].includes(event.eventType)) continue
    const id = activityId(event)
    const previous = grouped.get(id)
    const status = event.eventType === 'tool_started'
      ? 'running'
      : event.eventType === 'tool_failed' || event.payload.ok === false ? 'failed' : event.eventType === 'tool_cancelled' ? 'cancelled' : 'completed'
    const startedAt = previous?.startedAt || (event.eventType === 'tool_started' ? event.occurredAt : undefined)
    const failure = event.payload.failure && typeof event.payload.failure === 'object' && !Array.isArray(event.payload.failure) ? event.payload.failure as Record<string, unknown> : undefined
    grouped.set(id, {
      id,
      label: typeof event.payload.tool_name === 'string' || typeof event.payload.capability === 'string' ? TOOL_LABELS[toolName(event)] || toolName(event).replaceAll('_', ' ') : previous?.label || toolName(event),
      source: typeof event.payload.binding_id === 'string' || typeof event.payload.capability === 'string' ? activitySource(event) : previous?.source || activitySource(event),
      status,
      ...(failure ? { failure: { code: typeof failure.code === 'string' ? failure.code : undefined, message: typeof failure.message === 'string' ? failure.message : undefined, summary: typeof failure.summary === 'string' ? failure.summary : undefined } } : previous?.failure ? { failure: previous.failure } : {}),
      taskStepId: typeof event.payload.task_step_id === 'string' ? event.payload.task_step_id : previous?.taskStepId,
      taskStepNumber: typeof event.payload.task_step_number === 'number' ? event.payload.task_step_number : previous?.taskStepNumber,
      stepToolNumber: typeof event.payload.step_tool_number === 'number' ? event.payload.step_tool_number : previous?.stepToolNumber,
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
    const capacity=capacityFailureNotice(event.payload)
    if(capacity)return capacity
    const detail = terminalDetail(event)
    const code = typeof event.payload.error_code === 'string' ? event.payload.error_code : undefined
    return `**执行失败**\n\n${detail || attemptFailureCopy(code)}${detail && code ? `\n\n诊断代码：${code}` : ''}`
  }
  if (event.eventType === 'attempt_cancelled') return '**本次 Attempt 已取消**\n\n可以修改指令后重新发送。'
  return '**本次 Attempt 已中断**\n\n可以查看执行过程，并在确认模型上下文后重新运行。'
}

export function projectAssistantMessages(events: readonly EventEnvelope[], instructionModels: readonly { contextId: string; modelId: string }[] = []): ThreadMessageLike[] {
  const models = new Map(instructionModels.map(model => [model.contextId, model.modelId]))
  const runtimeModes = new Map<string, RuntimeMode>()
  const nativeAttempts = new Set(events.filter(event => event.payload.source === 'native_conversation').map(event => event.attemptId || event.turnId))
  for (const event of events) {
    const attempt = event.attemptId || event.turnId
    if (event.eventType === 'command_accepted' && attempt) {
      runtimeModes.set(attempt, event.payload.runtime_mode === 'pi_reference' ? 'pi_reference' : 'capstone')
    }
    for (const key of ['model_context', 'previous_context', 'restored_context']) {
      const context = event.payload[key]
      if (context && typeof context === 'object' && !Array.isArray(context)) {
        const document = context as Record<string, unknown>
        if (typeof document.id === 'string' && typeof document.model_id === 'string') models.set(document.id, document.model_id)
      }
    }
  }
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
        messages.push({ id: `user-${event.eventId}`, role: 'user', content: text, metadata: { custom: { mode: commandMode(event), eventId: event.eventId, attemptId: key, attachmentRefs:stringRefs(event.payload.attachment_refs), modelId: event.modelContextId ? models.get(event.modelContextId) : undefined, sentAt: event.occurredAt, receipt: `${commandMode(event)} · accepted` } } })
      }
      const key=event.attemptId||event.turnId
      if(key)ensureAssistant(key)
      continue
    }
    if (event.eventType === 'attempt_started') {
      const key = event.attemptId || event.turnId
      if (key) ensureAssistant(key, event.occurredAt)
      continue
    }
    if(event.eventType==='native_artifact_published'&&projectNativeArtifacts([event]).length){
      ensureAssistant(event.attemptId!)
      continue
    }
    if (event.eventType === 'assistant_text_delta') {
      const key = event.attemptId || event.turnId || `event-${event.eventId}`
      ensureAssistant(key).content += payloadText(event)
      continue
    }
    if(event.visibility==='public'&&event.eventType==='assistant_thinking_delta'&&event.attemptId&&typeof event.payload.text==='string') {
      ensureAssistant(event.attemptId)
      continue
    }
    if (event.eventType === 'attempt_completed' || event.eventType === 'attempt_failed' || event.eventType === 'attempt_cancelled' || event.eventType === 'attempt_interrupted') {
      const key = event.attemptId || event.turnId
      let message = key ? assistantByAttempt.get(key) : undefined
      const delivered = event.eventType === 'attempt_completed' ||
        (event.eventType === 'attempt_failed' && typeof event.payload.outcome === 'object' && event.payload.outcome !== null)
      const answer = delivered && typeof event.payload.answer === 'string'
        ? event.payload.answer
        : ''
      const terminalAnswer = delivered ? answer : terminalContent(event)
      const capacityNotice=event.eventType==='attempt_failed'?capacityFailureNotice(event.payload):undefined
      if (!message && key) message = ensureAssistant(key, key ? startedAtByAttempt.get(key) : undefined)
      const partialText = event.eventType !== 'attempt_completed' ? message?.content : undefined
      if (message && terminalAnswer && (delivered || !message.content)) {
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
            ...(capacityNotice?{terminalNotice:capacityNotice,partialText:delivered?answer:partialText}:!delivered ? { terminalNotice: terminalAnswer, partialText } : {}),
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
      content: `本次 Attempt ${label}。可以查看执行过程，并在确认模型上下文后重新运行。`,
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
    const runtimeMode = attemptId ? runtimeModes.get(attemptId) || 'capstone' : 'capstone'
    const activities = attemptId ? projectAssistantActivity(events.filter((candidate) => candidate.attemptId === attemptId)) : []
    const acceptedContext = events.find(event => event.attemptId === attemptId && event.eventType === 'turn_plan_created')?.payload.accepted_context
    const failureResults = events.filter((event) => event.attemptId === attemptId &&
      ((event.eventType === 'tool_completed' && event.payload.ok === false) ||
       (event.eventType === 'validation_observation' && event.payload.status === 'failed')))
      .map((event) => {
        const failure = event.payload.failure && typeof event.payload.failure === 'object'
          ? event.payload.failure as Record<string, unknown> : event.payload
        return { id: event.eventId, kind: event.eventType === 'tool_completed' ? 'execution' : 'validation',
        tool: typeof event.payload.tool_name === 'string' ? event.payload.tool_name : '',
        message: typeof failure.message === 'string' ? failure.message : '',
        code: typeof failure.code === 'string' ? failure.code : '',
        phase: typeof failure.phase === 'string' ? failure.phase : '',
        sequence: event.eventSeq }
      })
    const toolExecutions: ToolExecutionRecord[] = events.filter(event => event.attemptId === attemptId &&
      event.eventType === 'tool_completed' && typeof event.payload.ok === 'boolean' &&
      typeof event.payload.capability === 'string' && event.payload.request_parameters &&
      typeof event.payload.request_parameters === 'object' && !Array.isArray(event.payload.request_parameters))
      .map(event => ({ id: typeof event.payload.tool_call_id === 'string' ? event.payload.tool_call_id : event.eventId,
        tool: typeof event.payload.tool_name === 'string' ? event.payload.tool_name : '',
        capability: event.payload.capability as string, ok: event.payload.ok as boolean,
        parameters: event.payload.request_parameters as Record<string, unknown>,
        resultRefs: stringRefs(event.payload.result_refs), evidenceRefs: stringRefs(event.payload.evidence_refs), sequence: event.eventSeq }))
    const research = events.filter(event => event.attemptId === attemptId && event.eventType === 'research_state_updated').at(-1)
    const retainedResearchGoal = typeof research?.payload.goal === 'string' ? research.payload.goal : undefined
    const parsedResearch = parseResearchSnapshot(research?.payload.research_snapshot)
    const researchSnapshot = parsedResearch && parsedResearch.research_id === research?.payload.research_id &&
      parsedResearch.revision === research.payload.research_revision && parsedResearch.goal === research.payload.goal ? parsedResearch : undefined
    const taskProgress = attemptId ? projectTaskProgress(events, attemptId) : []
    const taskSteps = attemptId ? projectTaskSteps(events, attemptId) : []
    const stepDiagnostics = attemptId ? projectTaskStepDiagnostics(events, attemptId) : []
    const researchBranches = attemptId ? projectResearchBranches(events, attemptId) : []
    const executionGraph = attemptId ? projectExecutionGraph(events, attemptId) : undefined
    const researchGoal=executionGraph?.current.goal??taskProgress.find(item=>item.kind==='goal')?.text
    const modelRequests = attemptId ? projectProcessModelRequests(events, attemptId) : []
    const firstCheckpoint=executionGraph?.checkpoints[0]?.checkpoint.ref
    const organizationEvent=attemptId?events.find(event=>{
      if(event.attemptId!==attemptId||event.visibility!=='public')return false
      if(projectTaskSteps([event],attemptId).some(step=>!isExecutionLifecycleStep(step.id)))return true
      const progress=event.payload.research_graph as {checkpoint?:{ref?:unknown}}|undefined
      return Boolean(firstCheckpoint&&progress?.checkpoint?.ref===firstCheckpoint)
    }):undefined
    const executionEvent=attemptId?events.find(event=>{
      if(event.attemptId!==attemptId||event.visibility!=='public')return false
      if(event===organizationEvent)return true
      if(['tool_started','tool_completed','tool_failed','tool_cancelled'].includes(event.eventType)&&toolName(event)!=='agent_task_progress')return true
      const native=nativeToolActivity(event)
      return Boolean(native&&native.name!=='agent_task_progress')
    }):undefined
    const initialProjection=attemptId?projectInitialThinking(events,attemptId,executionEvent?.eventSeq,organizationEvent?.eventSeq??Infinity):undefined
    const initialThinking=nativeAttempts.has(attemptId)&&initialProjection?.handedOff&&modelRequests.some(call=>call.thinking)?undefined:initialProjection
    const withMetadata = { ...message, metadata: { custom: { ...custom, activities, modelRequests, initialThinking, nativeGraphFocus: nativeGraphFocus(executionGraph) ?? (nativeAttempts.has(attemptId) ? 'tools' : undefined), runtimeMode, acceptedContext, failureResults, researchGoal, retainedResearchGoal, researchSnapshot, toolExecutions, taskProgress, taskSteps, stepDiagnostics, researchBranches, executionGraph, stepStorageKey: `${events[0]?.threadId ?? ''}:${attemptId ?? ''}` } } }
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

export const MarkdownMessage = MarkdownContent

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

function ChatActions({ evidenceOpen = false, onShowEvidence, onShowNetwork, role, text, evidenceRefs, evidenceState = 'not_applicable', contextId, selectionRevision, toolCount, processAvailable, resultAvailable, resultOpen, onShowResult, onRegenerate, onShowActivity, activityOpen, showActivity, attemptId = '', resultRefs = [], projections = [], failures = [], executions = [], researchSnapshot, onSelectResult, answerLabel = '本次回答', onCloseEvidence }: { answerLabel?: string; onCloseEvidence?: () => void; evidenceOpen?: boolean; onShowEvidence?: () => void; networkSelected?: boolean; onShowNetwork?: () => void; role: string; text: string; evidenceRefs: string[]; evidenceState?: AnswerEvidenceState; contextId?: string; selectionRevision?: string; toolCount: number; processAvailable?: boolean; resultAvailable?: boolean; resultOpen?: boolean; onShowResult?: () => void; onRegenerate?: () => Promise<void>; onShowActivity?: () => void; activityOpen?: boolean; showActivity?: boolean; attemptId?: string; resultRefs?: string[]; projections?: readonly ResultProjection[]; failures?: readonly FailureEvidence[]; executions?: readonly ToolExecutionRecord[]; researchSnapshot?: ResearchSnapshot; onSelectResult?: (resultId: string) => void }) {
  const [copied, setCopied] = useState(false)
  const readRecords = useContext(AttemptRecordsContext)
  const evidenceAvailable = evidenceState === 'available' && evidenceRefs.length > 0
  const copy = async () => {
    if (await copyToClipboard(text)) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    }
  }
  if (role === 'user') {
    return <div className="capstone-chat-actions" aria-label="消息操作"><IconAction label={copied ? '已复制' : '复制指令'} onClick={() => void copy()}>{copied ? <Check /> : <Copy />}</IconAction></div>
  }
  return <>
  <div className="capstone-chat-actions" aria-label="回答操作">
    <IconAction label={copied ? '已复制' : '复制回答'} onClick={() => void copy()}>{copied ? <Check /> : <Copy />}</IconAction>
    {onShowNetwork && <IconAction label="查看此指令电网图" onClick={onShowNetwork}><Network /></IconAction>}
    {resultAvailable && onShowResult && <IconAction label="查看计算结果" expanded={resultOpen} onClick={onShowResult}><Activity /></IconAction>}
    {evidenceAvailable && onShowEvidence && <IconAction label="查看推演证据" description={researchSnapshot && evidenceState !== 'available' ? '查看已保存的研究判断与工作记录' : failures.length > 0 && evidenceState !== 'available' ? '查看已保存的执行或核验失败记录' : evidenceStateCopy[evidenceState]} evidenceState={evidenceState} expanded={evidenceOpen} onClick={onShowEvidence}><FileCheck2 /></IconAction>}
    {showActivity !== false && (toolCount > 0 || processAvailable || Boolean(readRecords && attemptId)) && onShowActivity && <IconAction label="查看执行过程" expanded={activityOpen} onClick={onShowActivity}><ListTree /></IconAction>}
    {onRegenerate && <IconAction label="重试本次指令" onClick={() => void onRegenerate()}><RotateCcw /></IconAction>}
  </div>
  {evidenceAvailable && evidenceOpen && <AnswerDetailSheet title="推演依据" answerLabel={answerLabel} onClose={() => onCloseEvidence?.()}>
    {readRecords && attemptId && <AttemptRecordPanel key={attemptId} attemptId={attemptId} read={readRecords} />}
    <ResearchEvidence snapshot={researchSnapshot} />
    <InferenceEvidencePanel attemptId={attemptId} admitted={evidenceState === 'available'} resultRefs={resultRefs}
      evidenceRefs={evidenceRefs} projections={projections} failures={failures} executions={executions} onSelectResult={onSelectResult} />
    {contextId && <details className="capstone-evidence-trace"><summary>任务身份</summary>
      <p>模型上下文 {contextId}{selectionRevision ? ` · selection ${selectionRevision}` : ''}</p></details>}
  </AnswerDetailSheet>}
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

function ToolDiagnostic({ diagnostic }: { diagnostic: string }) {
  const [hovered, setHovered] = useState(false)
  const [pinned, setPinned] = useState(false)
  const open = hovered || pinned
  const trigger = useRef<HTMLButtonElement>(null)
  const tooltip = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState({ left: 12, top: 12 })
  useLayoutEffect(() => {
    if (!open || !trigger.current || !tooltip.current) return
    const anchor = trigger.current.getBoundingClientRect()
    const box = tooltip.current.getBoundingClientRect()
    const left = Math.max(12, Math.min(anchor.left, window.innerWidth - box.width - 12))
    const below = anchor.bottom + 6
    const top = below + box.height <= window.innerHeight - 12 ? below
      : Math.max(12, anchor.top - box.height - 6)
    setPosition({ left, top })
  }, [open, diagnostic])
  useEffect(() => {
    if (!open) return
    const close = (event: Event) => {
      if (event.target instanceof Node && tooltip.current?.contains(event.target)) return
      setHovered(false); setPinned(false)
    }
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => { window.removeEventListener('scroll', close, true); window.removeEventListener('resize', close) }
  }, [open])
  return <span className="capstone-tool-diagnostic" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
    <button ref={trigger} type="button" aria-label="查看原始诊断" aria-expanded={open}
      onFocus={() => setHovered(true)} onBlur={() => setHovered(false)}
      onClick={() => setPinned((current) => !current)}
      onKeyDown={(event) => { if (event.key === 'Escape') { setPinned(false); setHovered(false) } }}>原始诊断</button>
    {open && createPortal(<div ref={tooltip} role="tooltip" className="capstone-tool-diagnostic-popover"
      style={position}>{diagnostic}</div>, document.body)}
  </span>
}

function ActivityItems({ activities }: { activities: ChatActivity[] }) {
  const interval = (item: ChatActivity) => [Date.parse(item.startedAt ?? ''), item.finishedAt ? Date.parse(item.finishedAt) : item.status === 'running' ? Infinity : NaN]
  return <div className="capstone-chat-activity-list">{activities.map((item) => {
    const [owner, ...detail] = item.source.split(' · ')
    const reason = toolFailureReason(item.failure)
    const diagnostic = [reason, item.failure?.code ? `诊断：${item.failure.code}` : '',
      item.failure?.message ? `原文：${item.failure.message}` : ''].filter(Boolean).join('\n')
    const [start, end] = interval(item)
    const parallel = activities.some(other => {
      if (other.id === item.id) return false
      const [otherStart, otherEnd] = interval(other)
      return start < end && otherStart < otherEnd && start < otherEnd && otherStart < end
    })
    return <div key={item.id} className={`capstone-chat-activity-item is-${item.status}`}>
      <span className="capstone-chat-activity-icon" aria-hidden="true" />
      <div className="capstone-tool-call-content">
        <div className="capstone-tool-call-heading">
          <strong>{item.taskStepNumber !== undefined && item.stepToolNumber !== undefined ? `${String(item.taskStepNumber).padStart(2, '0')}.${item.stepToolNumber} ` : ''}{item.label}</strong>
          <small>{item.status === 'running' ? '执行中' : item.status === 'failed' ? '失败' : item.status === 'cancelled' ? '已停止' : '完成'}</small>
          {parallel && <small title="调用记录的时间区间重叠。">并行调用</small>}
        </div>
        <small><span className="capstone-chat-activity-source" data-owner={owner}>{owner.toUpperCase()}</span> {detail.join(' · ')}{item.durationMs === undefined ? '' : ` · ${formatDuration(item.durationMs)}`}</small>
        {item.operation && <div className="capstone-tool-operation">{item.operation}</div>}
        {item.outputExcerpt && <details className="capstone-tool-output"><summary>查看返回摘要</summary><p>{item.outputExcerpt}</p><small>此处为有限长度摘要，可能截断。</small></details>}
        {owner==='pi'&&!item.operation&&!item.outputExcerpt&&<small>此调用回执未提供操作与返回摘要。</small>}
        {item.status === 'failed' && <div className="capstone-tool-failure-line">
          <span className="capstone-tool-failure-reason" title={diagnostic}>{reason ? reason.length > 180 ? reason.slice(0, 180) + '…' : reason : toolFailureCopy(item.failure?.code)}</span>
          {item.failure?.message && <ToolDiagnostic diagnostic={diagnostic} />}
        </div>}
      </div>
    </div>
  })}</div>
}

function TaskProgressItems({ items }: { items: readonly TaskProgress[] }) {
  const labels = { goal: '目标', observation: '观察', adjustment: '调整', limitation: '限制' }
  return <div className="capstone-task-progress" aria-label="任务进展">{items.map(item => <section key={item.id} data-sequence={item.sequence}>
    <p>{item.kind && item.kind !== 'observation' && <small>{labels[item.kind]}： </small>}{item.text}</p>
    {item.refs.length > 0 && <details><summary>关联引用 · {item.refs.length} 条</summary><small>记录中的引用不等于结论核验通过。</small>{item.refs.map(ref => <code key={ref}>{ref}</code>)}</details>}
  </section>)}</div>
}

function AttemptActivity({ activities, modelRequests = [], initialThinking, nativeGraphFocus: selectedGraphFocus, executionGraph, diagnostics: legacyDiagnostics = [], branches: legacyBranches = [], progress: legacyProgress = [], steps: legacySteps = [], stepStorageKey = '', goal, running, phase, open, onOpenChange, startedAt, durationMs, detailsRef, auxiliary, hasAuxiliary = false }: { activities: ChatActivity[]; modelRequests?: ProcessModelCall[]; initialThinking?: InitialThinking; nativeGraphFocus?: 'tools' | 'tasks'; executionGraph?: ExecutionGraph; diagnostics?: readonly TaskStepDiagnostic[]; branches?: readonly ResearchBranch[]; progress?: readonly TaskProgress[]; steps?: readonly TaskStep[]; stepStorageKey?: string; goal?: string; running: boolean; phase?: string; open: boolean; onOpenChange: (open: boolean) => void; startedAt?: string; durationMs?: number; detailsRef: React.RefObject<HTMLDetailsElement | null>; auxiliary?: ReactNode; hasAuxiliary?: boolean }) {
  const steps = executionGraph ? [] : legacySteps.filter(step=>!isExecutionLifecycleStep(step.id))
  const lifecycleSteps = executionGraph ? [] : legacySteps.filter(step=>isExecutionLifecycleStep(step.id))
  const branches = executionGraph ? [] : legacyBranches
  const progress = executionGraph ? [] : legacyProgress
  const diagnostics = executionGraph ? [] : legacyDiagnostics
  const [reading, setReading] = useState(false)
  const [inlineToolsOpen,setInlineToolsOpen]=useState(false),[readerToolsOpen,setReaderToolsOpen]=useState(true)
  const [disclosureStates,setDisclosureStates]=useState([{canExpand:false,canCollapse:false},{canExpand:false,canCollapse:false}])
  const embeddedScroll = useRef(0)
  const restoreEmbeddedScroll = useRef(false)
  const readerContent = useRef<HTMLDivElement>(null)
  const openReader = () => { embeddedScroll.current = processViewport.current?.scrollTop ?? 0; setReaderToolsOpen(true);setReading(true) }
  const closeReader = () => { restoreEmbeddedScroll.current = true; setReading(false) }
  const foldTools=(expanded:boolean,value:boolean)=>{
    const root=expanded?readerContent.current:processViewport.current
    root?.querySelectorAll<HTMLDetailsElement>('details.capstone-call-tool').forEach(node=>{node.open=value})
    root?.querySelectorAll<HTMLButtonElement>('.capstone-thinking-trigger').forEach(button=>{
      if(button.getAttribute('aria-expanded')!==String(value))button.click()
    })
    if(expanded)setReaderToolsOpen(value);else setInlineToolsOpen(value)
  }
  const toolControls=(expanded:boolean)=><span className="capstone-process-controls" role="group" aria-label="思考与工具详情显示"><button type="button" aria-label="展开工具详情" disabled={!disclosureStates[+expanded].canExpand} title="展开全部 Thinking 与工具详情" onClick={event=>{event.preventDefault();event.stopPropagation();foldTools(expanded,true)}}><ChevronsUpDown aria-hidden="true"/></button><button type="button" aria-label="折叠工具详情" disabled={!disclosureStates[+expanded].canCollapse} title="折叠全部 Thinking 与工具详情" onClick={event=>{event.preventDefault();event.stopPropagation();foldTools(expanded,false)}}><ChevronsDownUp aria-hidden="true"/></button></span>
  const toolActivities = executionGraph || selectedGraphFocus === 'tools' ? activities : activities.filter(item => !item.source.includes('agent_task_progress') || item.status === 'failed')
  const taskGoal = executionGraph?.current.goal ?? progress.find(item => item.kind === 'goal')?.text ?? goal
  const goalText = taskGoal?.replace(/^(?:任务目标|研究目标|目标)\s*[:：]\s*/u, '')
  const graphToolIds = new Set(executionGraph?.executions.flatMap(execution => execution.tools.map(tool => tool.id)))
  const callId = (activity: ChatActivity): string => {
    if (!activity.id.startsWith('native:')) return activity.id
    try { const parts: unknown = JSON.parse(activity.id.slice('native:'.length)); return Array.isArray(parts) && typeof parts[3] === 'string' ? parts[3] : activity.id } catch { return activity.id }
  }
  const graphUnassignedTools = toolActivities.filter(activity => !graphToolIds.has(callId(activity)))
  const toolCount = executionGraph ? graphToolIds.size + graphUnassignedTools.length : toolActivities.length
  const focus = selectedGraphFocus === 'tools' && !executionGraph ? (toolCount > 0 ? 'tools' : 'thinking') : executionGraph && selectedGraphFocus ? selectedGraphFocus : executionGraph || steps.length > 0 || branches.length > 0 ? 'tasks' : toolCount > 0 ? 'tools' : 'thinking'
  const followLightweight=running&&focus==='tools'&&selectedGraphFocus==='tools'
  const processOpen=open||followLightweight
  const processViewport = useRef<HTMLDivElement>(null)
  useLayoutEffect(()=>{
    const roots=[processViewport.current,readerContent.current]
    const measure=()=>{
      const next=roots.map(root=>{
        const states=[...(root?.querySelectorAll<HTMLDetailsElement>('details.capstone-call-tool')??[])].map(node=>node.open)
        states.push(...[...(root?.querySelectorAll<HTMLButtonElement>('.capstone-thinking-trigger')??[])].map(node=>node.getAttribute('aria-expanded')==='true'))
        return {canExpand:states.some(value=>!value),canCollapse:states.some(Boolean)}
      })
      setDisclosureStates(previous=>previous.every((state,index)=>state.canExpand===next[index].canExpand&&state.canCollapse===next[index].canCollapse)?previous:next)
    }
    measure()
    const observer=new MutationObserver(measure)
    roots.forEach(root=>{if(root)observer.observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['open','aria-expanded']})})
    return()=>observer.disconnect()
  })
  const followProcess = useRef(true)
  useLayoutEffect(() => {
    const node = processViewport.current
    const viewport = node?.closest<HTMLElement>('.capstone-chat-viewport')
    if (!node || !viewport) return
    const measure = () => {
      const bounds = viewport.getBoundingClientRect()
      const bottom = Math.min(bounds.bottom, window.innerHeight)
      const available = Math.max(0, bottom - node.getBoundingClientRect().top - 12)
      const maximum = Math.max(80, Math.min(bounds.height * .72, window.innerHeight * .65))
      node.style.maxHeight = `${Math.min(maximum, Math.max(80, available))}px`
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(viewport)
    viewport.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    return () => { observer?.disconnect(); viewport.removeEventListener('scroll', measure); window.removeEventListener('resize', measure) }
  }, [running, activities, progress, steps, open])
  const observeProcessScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const node = event.currentTarget
    followProcess.current = node.scrollHeight - node.clientHeight - node.scrollTop < 20
  }
  useLayoutEffect(() => {
    const node = processViewport.current
    if (!reading && node && restoreEmbeddedScroll.current) { node.scrollTop = embeddedScroll.current; restoreEmbeddedScroll.current = false; return }
    if (!reading && running && node && followProcess.current) node.scrollTop = Math.max(0, node.scrollHeight - node.clientHeight)
  }, [running, activities, progress, steps, open, reading])
  const [traceFocus, setTraceFocus] = useState<GraphTraceFocus>()
  const traceIssues = executionGraph ? graphTraceIssues(executionGraph, phase) : []
  const [foldCommand, setFoldCommand] = useState<StepFoldCommand>()
  const foldSteps = executionGraph ? executionGraph.current.nodes : steps
  const [stepOpenStates, setStepOpenStates] = useState<Record<string, boolean>>({})
  const reportFold = useCallback((id: string, value: boolean) => {
    const key = `${stepStorageKey}:${id}`
    setStepOpenStates(previous => previous[key] === value ? previous : { ...previous, [key]: value })
  }, [stepStorageKey])
  const isStepOpen = (id: string) => stepOpenStates[`${stepStorageKey}:${id}`] ?? readStepOpen(stepStorageKey, id)
  const foldAll = (value: boolean) => {
    const updates: Record<string, boolean> = {}
    for (const step of foldSteps) { saveStepOpen(stepStorageKey, step.id, value); updates[`${stepStorageKey}:${step.id}`] = value }
    setStepOpenStates(previous => ({ ...previous, ...updates }))
    setFoldCommand(previous => ({ open: value, revision: (previous?.revision ?? 0) + 1 }))
  }
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  const liveDuration = startedAt ? durationBetween(startedAt, new Date(now).toISOString()) : undefined
  const elapsed = running ? liveDuration : durationMs
  const hasProcess = Boolean(initialThinking) || running || modelRequests.length > 0 || !!startedAt || !!executionGraph || activities.length > 0 || progress.length > 0 || steps.length > 0 || lifecycleSteps.length > 0 || diagnostics.length > 0 || branches.length > 0
  const modelMs = modelRequests.reduce((sum,call)=>sum+(call.finishedAt ? call.ms : running&&!call.settled ? modelCallMs(call,now) : 0),0)
  const incompleteModelTime = modelRequests.some(call=>!call.finishedAt&&(!running||call.settled))
  const pooled=modelRequests.flatMap(call=>call.poolCalls??[]),poolSummary=summarizeLlmPoolCalls(pooled)
  const modelSummary = modelRequests.length > 0 ? <><span title="累计父模型响应区间，包含请求等待与生成；不含子调用，不等于整轮总耗时。"> · LLM {modelRequests.length} 次 · 累计 {incompleteModelTime?'≥ ':''}{formatDuration(modelMs)}</span>{pooled.length>0&&<span title="只累计子调用实际报告的模型响应；不含排队和依赖等待，不计入父模型耗时。"> · 子 LLM {poolSummary.responses??'—'} 次 · 响应累计 {poolSummary.responseMs===undefined?'未完整记录':formatDuration(poolSummary.responseMs)}</span>}</> : null
  if (!hasProcess && !hasAuxiliary) return null
  const terminalLabel = phase === 'failed' ? '执行失败 ·' : phase === 'cancelled' ? '已取消 ·' : phase === 'interrupted' ? '已中断 ·' : '已完成'
  const terminalClass = phase === 'failed' || phase === 'interrupted' ? ` is-${phase}` : phase === 'cancelled' ? ' is-cancelled' : ''
  const lastWork = !running && !open && ['failed', 'interrupted', 'cancelled'].includes(phase ?? '')
    ? progress.filter(item => item.kind !== 'goal').at(-1) : undefined
  const lifecycleDetails = lifecycleSteps.length > 0 && <details className="capstone-native-tool-calls"><summary>运行阶段与计时</summary>
    {lifecycleSteps.map(step=><p className="capstone-task-goal" key={step.id}><span>{step.title}</span> · {step.status === 'running' ? running ? '进行中' : '结束状态未记录' : step.status === 'completed' ? '已结束' : step.status === 'cancelled' ? '已停止' : step.status === 'failed' ? '失败' : '受限'} · <span>{step.durationMs === undefined ? '耗时未记录' : formatDuration(step.durationMs)}</span></p>)}
  </details>
  const graphProcess = (expandedResearch = false) => executionGraph && <><ExecutionGraphProcess attemptStartedAt={startedAt} attemptDurationMs={durationMs} overallTools={toolActivities.map(activity=>({...activity,id:callId(activity),name:activity.source,
    status:activity.status==='cancelled'?'failed':activity.status,origin:'parent' as const}))} traceFocus={traceFocus} graph={executionGraph} storageKey={expandedResearch ? `${stepStorageKey}:reader` : stepStorageKey} attemptPhase={phase} expandedResearch={expandedResearch} showFoldControls={expandedResearch} foldCommand={expandedResearch ? undefined : foldCommand} onFoldChange={expandedResearch ? undefined : reportFold} now={running ? now : undefined} />
    {graphUnassignedTools.length > 0 && <details className="capstone-graph-control-tools"><summary>图控制与未归属工具 · {graphUnassignedTools.length} 次</summary>{graphUnassignedTools.map(activity => {
      const control = executionGraph.controlCalls.find(control => control.callId === callId(activity))
      return <div key={activity.id}>{control ? <p>图控制 · <code>{control.graphRef}</code> · 检查点 v{control.checkpoint.revision}</p> : <p>未记录确切图版本关联</p>}<ActivityItems activities={[activity]} /></div>
    })}</details>}</>
  const process = (expandedResearch = false) => {
    if (focus === 'thinking') return <>
      {modelRequests.length > 0 && <ProcessCallTrace models={modelRequests} tools={[]} now={running ? now : undefined} active={running} />}
      {lifecycleDetails}
    </>
    if (focus === 'tools' && executionGraph) return <>
      <section aria-label="工具调用过程">
        {executionGraph.executions.map(execution=><ProcessCallTrace key={execution.action.id} models={[]} tools={execution.tools} active={running&&!execution.nativeStatus} now={running?now:undefined} renderToolDetails={tool=>{
          const record=execution.tools.find(item=>item.id===tool.id)
          return record?.output&&<RecordedResult text={record.output} title={record.name}/>
        }}/>) }
        <ActivityItems activities={graphUnassignedTools.filter(activity=>!executionGraph.controlCalls.some(control=>control.callId===callId(activity)))} />
      </section>
      <details className="capstone-native-tool-calls"><summary>任务组织记录</summary>{graphProcess(expandedResearch)}</details>
    </>
    if (focus === 'tools') return <section aria-label="工具调用过程">{modelRequests.length > 0 ? <ProcessCallTrace compact expandedThinking={expandedResearch} expandedTools={expandedResearch?readerToolsOpen:inlineToolsOpen} models={modelRequests} tools={toolActivities.map(activity=>({id:callId(activity),name:activity.label,status:activity.status,startedAt:activity.startedAt,finishedAt:activity.finishedAt,durationMs:activity.durationMs,operation:activity.operation}))} now={running ? now : undefined} active={running} renderToolDetails={tool=>{
      const activity=toolActivities.find(item=>callId(item)===tool.id)
      return <>{activity?.failure&&<p className="capstone-tool-failure-line">{toolFailureReason(activity.failure)||toolFailureCopy(activity.failure.code)}</p>}{activity?.outputExcerpt&&<p className="capstone-tool-operation">{activity.outputExcerpt}</p>}</>
    }}/> : <ActivityItems activities={toolActivities} />}
      {lifecycleDetails}
    </section>
    if (executionGraph) return graphProcess(expandedResearch)
    const readerTools = (items: ChatActivity[]) => <>
      {items.filter(item => item.status === 'failed').map(item => <StepErrorDetails key={item.id} label={`${item.label}：调用失败`} reason={item.failure?.summary || item.failure?.message || '未记录具体原因，可展开工具明细查看。'} />)}
      <details className="capstone-native-tool-calls capstone-unassigned-tool"><summary>工具明细 · 未归属步骤</summary><ActivityItems activities={items} /></details>
    </>
    if(steps.length === 0)return <>
      <TaskProgressItems items={progress.filter(item=>item.stepId||item.kind==='goal')} />
      <p className="capstone-task-goal">当前记录未提供任务计划。</p>
      {expandedResearch ? readerTools(toolActivities) : <details className="capstone-native-tool-calls"><summary>工具调用明细 · {toolActivities.length}</summary><ActivityItems activities={toolActivities}/></details>}
    </>
    const entries = [
      ...steps.map(step => ({ id: `step:${step.id}`, at: step.startedAt, step, activity: undefined as ChatActivity | undefined })),
      ...toolActivities.filter(item => !item.taskStepId).map(activity => ({ id: `tool:${activity.id}`, at: activity.startedAt, step: undefined as TaskStep | undefined, activity })),
    ].sort((left, right) => (left.at ? Date.parse(left.at) : Infinity) - (right.at ? Date.parse(right.at) : Infinity))
    return <>{entries.map(entry => entry.step ?
      <TaskStepProcess key={entry.id} steps={[entry.step]} branches={branches} storageKey={expandedResearch ? `${stepStorageKey}:reader` : stepStorageKey} running={running} expandedResearch={expandedResearch}
        stepNumbers={Object.fromEntries(steps.map(step => [step.id, step.number]))}
        foldCommand={expandedResearch ? undefined : foldCommand} onFoldChange={expandedResearch ? undefined : reportFold}
        toolCount={stepId => toolActivities.filter(item => item.taskStepId === stepId).length}
        toolMs={stepId => toolExecutionMs(toolActivities.filter(item => item.taskStepId === stepId))}
        renderProgress={stepId => <><TaskProgressItems items={progress.filter(item => item.stepId === stepId && item.phase !== 'started' && !(item.kind === 'goal' && item.text === taskGoal))} />{toolActivities.filter(item => item.taskStepId === stepId && item.status === 'failed').map(item => <StepErrorDetails key={item.id} label={`${item.label}：调用失败`} reason={item.failure?.summary || item.failure?.message || '未记录具体原因，可展开工具明细查看。'} />)}</>}
        renderTools={stepId => <ActivityItems activities={toolActivities.filter(item => item.taskStepId === stepId)} />} /> :
      <div key={entry.id} title="未归属任务步骤">{expandedResearch ? readerTools(entry.activity ? [entry.activity] : []) : <ActivityItems activities={entry.activity ? [entry.activity] : []} />}</div>)}{lifecycleDetails}</>
  }
  return <>{reading && <AnswerDetailSheet title="执行过程" showAnswerLabel={false} headerActions={focus==='tools'&&toolCount>0?toolControls(true):undefined} answerLabel={goalText ? goalText.slice(0, 80) : '当前指令'} className="capstone-process-reader" onClose={closeReader} metadata={<span className="capstone-process-reader-status">{running ? '执行中' : phase === 'failed' ? '执行失败' : phase === 'cancelled' ? '已取消' : phase === 'interrupted' ? '已中断' : phase === 'completed' ? '已完成' : '执行状态未记录'}{toolCount>0?` · ${toolCount} 次工具调用`:''}{modelSummary}{elapsed === undefined ? '' : ` · 总耗时 ${formatDuration(elapsed)}`}</span>}>
    <div ref={readerContent} className="capstone-chat-activity-frame">
      {initialThinking&&<ThinkingProcess thinking={initialThinking} storageKey={stepStorageKey} now={now} expanded/>}
      {steps.length > 1 && <nav className="capstone-process-directory" aria-label="任务步骤目录">{steps.map(step => <button type="button" key={step.id} title={step.title} onClick={() => {
        const node = [...(readerContent.current?.querySelectorAll<HTMLElement>('[data-step-id]') ?? [])].find(node => node.dataset.stepId === step.id)
        node?.scrollIntoView({ block: 'start', behavior: 'smooth' })
      }}>{String(step.number).padStart(2, '0')} {step.title}</button>)}</nav>}
      {goalText && <p className="capstone-task-goal">{goalText}</p>}
      {diagnostics.map(item => <StepErrorDetails key={item.id} label="步骤未推进" reason={item.text} />)}
      <TaskProgressItems items={progress.filter(item => !item.stepId && item.kind !== 'goal')} />
      {process(true)}
      {branches.some(branch => !steps.some(step => step.id === branch.parentStepId)) && <ResearchBranchItems expandedResearch branches={branches.filter(branch => !steps.some(step => step.id === branch.parentStepId))} storageKey={`${stepStorageKey}:reader`} />}
      {hasAuxiliary && <aside className="capstone-process-auxiliary">{auxiliary}</aside>}
    </div>
  </AnswerDetailSheet>}{!hasProcess ? <button type="button" className="capstone-process-auxiliary-entry" aria-label="放大阅读执行过程" title="查看任务资料与记录" onClick={openReader}><Maximize2 aria-hidden="true" />任务资料与记录</button> : <div className={`capstone-chat-activity-frame${running ? ' is-running' : ' is-settled'}`} aria-busy={running}>{branches.some(branch => !steps.some(step => step.id === branch.parentStepId)) && <div aria-label="父步骤未在当前记录中的子分支"><ResearchBranchItems branches={branches.filter(branch => !steps.some(step => step.id === branch.parentStepId))} storageKey={stepStorageKey} /></div>}{diagnostics.map(item => <StepErrorDetails key={item.id} label="步骤未推进" reason={item.text} />)}<details ref={detailsRef} className={`capstone-chat-activity capstone-chat-activity-attached${terminalClass}`} open={processOpen} onToggle={event=>{if(followLightweight&&!event.currentTarget.open){event.currentTarget.open=true;return}onOpenChange(event.currentTarget.open)}}>
    <summary><Activity aria-hidden="true" /><span title={toolCount===0?'当前记录未提供可核对的工具调用数量，可查看执行过程。':undefined}>{running ? '正在执行' : terminalLabel} {focus === 'thinking' ? '思考状态' : <>{focus === 'tasks' && foldSteps.length > 0 ? `${foldSteps.length} 个任务步骤 · ` : ''}{toolCount>0?`${toolCount} 次工具调用`:'工具调用数未记录'}</>}{modelSummary}{elapsed === undefined ? '' : ` · 总耗时 ${formatDuration(elapsed)}`}</span>{traceIssues.length > 0 && <button type="button" className="capstone-process-trace-warning" aria-label="定位工具记录缺失" onClick={event => { event.preventDefault(); event.stopPropagation(); openReader(); setTraceFocus(previous => ({ ...traceIssues[0], revision: (previous?.revision ?? 0) + 1 })) }}><AlertTriangle aria-hidden="true" />工具记录缺失 · {traceIssues.reduce((sum, issue) => sum + issue.missingToolIds.length, 0)}项</button>}{!open && <small>查看执行过程</small>}<span className="capstone-process-toolbar">{processOpen&&focus==='tools'&&toolCount>0&&toolControls(false)}{open && focus === 'tasks' && foldSteps.length > 0 && <span className="capstone-process-controls" role="group" aria-label="步骤显示"><button type="button" aria-label="展开步骤" title="展开全部步骤" disabled={foldSteps.every(step => isStepOpen(step.id))} onClick={event => { event.preventDefault(); event.stopPropagation(); foldAll(true) }}><ChevronsUpDown aria-hidden="true" /></button><button type="button" aria-label="折叠步骤" title="折叠全部步骤" disabled={foldSteps.every(step => !isStepOpen(step.id))} onClick={event => { event.preventDefault(); event.stopPropagation(); foldAll(false) }}><ChevronsDownUp aria-hidden="true" /></button></span>}<button type="button" className="capstone-process-enlarge" title="放大阅读执行过程" aria-label="放大阅读执行过程" onClick={event => { event.preventDefault(); event.stopPropagation(); openReader() }}><Maximize2 aria-hidden="true" /></button></span></summary>
    {(!running || processOpen) && <div ref={processViewport} onScroll={observeProcessScroll} className="capstone-complete-process">{goalText && <p className="capstone-task-goal">{goalText}</p>}<TaskProgressItems items={progress.filter(item => !item.stepId && item.kind !== 'goal')} />{process()}</div>}
  </details>{executionGraph&&<ResearchProgressSummary nodes={executionGraph.current.nodes} limitations={[...progress.filter(item=>item.kind==='limitation').map(item=>item.text),...executionGraph.executions.flatMap(item=>item.tools.flatMap(tool=>tool.returnLimitations?.notes??[]))]} running={running}/ >}{lastWork && <div className="capstone-chat-activity-preview" aria-label="中断前的工作记录"><p className="capstone-task-goal">中断前的工作记录（不代表任务已完成）</p><TaskProgressItems items={[lastWork]} /></div>}{running && !processOpen && !executionGraph && <div ref={processViewport} onScroll={observeProcessScroll} className="capstone-chat-activity-preview" aria-label="执行过程预览">{goalText && <p className="capstone-task-goal">{goalText}</p>}<TaskProgressItems items={progress.filter(item => !item.stepId && item.kind !== 'goal')} />{process()}</div>}</div>}</>
}

function LegacyActivity({ activities, running }: { activities: ChatActivity[]; running: boolean }) {
  const [open, setOpen] = useState(false)
  const detailsRef = useRef<HTMLDetailsElement>(null)
  useEffect(() => {
    if (!running) setOpen(false)
  }, [running])
  return <AttemptActivity activities={activities} running={running} open={open} onOpenChange={setOpen} detailsRef={detailsRef} />
}

function resultCell(value: string | number | boolean | null): string {
  if (value === null) return '—'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  return String(value)
}

export function ResultProjectionCard({ projection, tableId, onFocusElement }: { projection: ResultProjection; tableId?: string; onFocusElement?: (projection: ResultProjection, elementId: string) => boolean | void }) {
  const statusLabel = projection.status === 'completed' ? '已完成' : projection.status === 'partial' ? '部分结果' : '暂不可用'
  return <section className={`capstone-result-card is-${projection.status}`} aria-label="结构化计算结果" data-result-id={projection.resultId} tabIndex={-1}>
    <div className="capstone-result-heading"><div><Activity aria-hidden="true" /><strong>计算结果</strong><span>{statusLabel}</span></div><small>{projection.source.capabilityId}</small></div>
    {projection.unavailableReason && <p className="capstone-result-reason">{projection.unavailableReason}</p>}
    {projection.summary.length > 0 && <div className="capstone-result-metrics">{projection.summary.map((metric) => <div key={metric.metricId}><span>{metric.label}</span><strong>{resultCell(metric.value)}{metric.unit ? ` ${metric.unit}` : ''}</strong></div>)}</div>}
    {projection.tables.filter(table => !tableId || table.tableId === tableId).map((table) => <div className="capstone-result-table-wrap" key={table.tableId}><div className="capstone-result-table-title">{table.title}</div><div className="capstone-result-table-scroll"><table><thead><tr>{table.columns.map((column) => <th key={column.columnId}>{column.label}{column.unit ? ` (${column.unit})` : ''}</th>)}</tr></thead><tbody>{table.rows.map((row) => <tr key={row.rowId}>{table.columns.map((column) => <td key={column.columnId}>{row.elementRef && onFocusElement && column === table.columns[0] ? <button type="button" className="capstone-result-element" onClick={() => onFocusElement?.(projection, row.elementRef!.elementId)} title="在拓扑图中定位">{resultCell(row.cells[column.columnId] ?? row.rowId)}</button> : resultCell(row.cells[column.columnId] ?? null)}</td>)}</tr>)}</tbody></table></div></div>)}
  </section>
}

function FoldableAnswer({ id, text, author, finishedAt }: { id: string; text: string; author: string; finishedAt?: string }) {
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
    <div className="capstone-answer-header"><span className="capstone-chat-role">{author}</span>
      {finishedAt && <InstructionTime value={finishedAt} completion />}
      {foldable && <button type="button" className={`capstone-answer-toggle${folded ? ' is-collapsed' : ''}`} aria-label={folded ? '展开完整回答' : '折叠回答'} title={folded ? '展开完整回答' : '收起回答'} aria-expanded={!folded} aria-controls={`${id}-content`} onClick={(event) => toggle(id, event.currentTarget)}>{folded ? <ChevronDown aria-hidden="true" /> : <ChevronUp aria-hidden="true" />}</button>}
    </div>
    <div className="capstone-answer-body">
      <div ref={body} id={`${id}-content`} className={`capstone-answer-content${folded ? ' is-collapsed' : ''}`} style={folded ? { maxHeight: previewHeight } : undefined} aria-hidden={folded || undefined} inert={folded || undefined}>
        <MarkdownMessage>{text}</MarkdownMessage>
      </div>
    </div>
    {folded && <span className="visually-hidden">{text.slice(0, 220)}…</span>}
  </div>
}

function HistoryAnswerActions({ disabled, onFold, onUnfold }: { disabled: boolean; onFold: () => void; onUnfold: () => void }) {
  const close = useCloseThreadSettings()
  return <div className="thread-history-actions" role="group" aria-label="历史回答整理">
    <button type="button" className="thread-settings-item" disabled={disabled} onClick={() => { onFold(); close() }}>折叠历史回答</button>
    <button type="button" className="thread-settings-item" disabled={disabled} onClick={() => { onUnfold(); close() }}>展开历史回答</button>
  </div>
}

function ChatMessage({ selectedNetworkAttempt, networkAttemptIds = [], onShowNetwork, onRegenerate, canRerunCompleted, modelSummary, showActivity = true, resultProjections, onFocusElement, onOpenTaskResults, nativeArtifacts = [], onOpenNativeArtifact }: { nativeArtifacts?:readonly NativeArtifact[]; onOpenNativeArtifact?:(artifact:NativeArtifact)=>void; onOpenTaskResults?: (product: TaskResultCollection) => void; onOpenResultProduct?: (result: ResultProjection) => void; selectedNetworkAttempt?: string; networkAttemptIds?: readonly string[]; onShowNetwork?: (attemptId: string) => void; onRegenerate?: (attemptId: string, instruction?: string) => Promise<void>; onFollowup?: (attemptId: string) => void; canRerunCompleted: boolean; modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string }; showActivity?: boolean; resultProjections?: readonly ResultProjection[]; onFocusElement?: (projection: ResultProjection, elementId: string) => boolean | void }) {
  const activityRef = useRef<HTMLDetailsElement>(null)
  const readRecords = useContext(AttemptRecordsContext)
  const role = useAuiState((state) => state.message.role)
  const content = useAuiState((state) => state.message.content)
  const id = useAuiState((state) => state.message.id)
  const { restoreAnchor, preserveControl } = useContext(AnswerReadingContext)
  const footerRef = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => restoreAnchor(id), [id, restoreAnchor])
  const status = useAuiState((state) => state.message.status)
  const custom = useAuiState((state) => state.message.metadata?.custom) as Record<string, unknown> | undefined
  const author = custom?.runtimeMode === 'pi_reference' ? 'Pi' : 'CAPSTONE'
  const hasText = messageText({ content }).trim().length > 0
  const text = messageText({ content })
  const attemptId = typeof custom?.attemptId==='string'?custom.attemptId:id.replace(/^assistant-/, '')
  const attemptResultProjections = resultProjections?.filter((item) => item.attemptId === attemptId) ?? []
  const attemptFiles=nativeArtifacts.filter(file=>file.attempt_id===attemptId)
  const failureResults = (Array.isArray(custom?.failureResults) ? custom.failureResults : []) as {
    id: string; kind: string; tool: string; message: string; code: string; phase: string; sequence: number;
  }[]
  const hasResults = attemptResultProjections.length > 0 || failureResults.length > 0
  const acceptedObjects = custom?.acceptedContext && typeof custom.acceptedContext === 'object' ? (custom.acceptedContext as { objects?: unknown }).objects : undefined
  const hasAuxiliary = Boolean(readRecords) || Boolean(Array.isArray(acceptedObjects) && acceptedObjects.length) || Boolean(parseResearchSnapshot(custom?.researchSnapshot)) || failureResults.length > 0 || Boolean(Array.isArray(custom?.toolExecutions) && custom.toolExecutions.length)
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
  const finishedAt = typeof custom?.finishedAt === 'string' ? custom.finishedAt : undefined
  const toolCount = typeof custom?.toolCount === 'number' ? custom.toolCount : 0
  const contextId = typeof custom?.modelContextId === 'string' ? custom.modelContextId : undefined
  const selectionRevision = typeof custom?.selectionRevision === 'string' ? custom.selectionRevision : undefined
  const answerModel = contextId === modelSummary?.contextId ? modelSummary : undefined
  const activities = Array.isArray(custom?.activities) ? custom.activities as ChatActivity[] : []
  const processStorageKey = `capstone-process-open:${typeof custom?.stepStorageKey === 'string' ? custom.stepStorageKey : attemptId}`
  const [activityOpen, setActivityOpen] = useState(() => {
    try { return localStorage.getItem(processStorageKey) === 'true' } catch { return false }
  })
  useEffect(() => {
    try { localStorage.setItem(processStorageKey, String(activityOpen)) } catch { /* Retain state in this page. */ }
  }, [activityOpen, processStorageKey])
  const detail = useContext(AnswerDetailContext)
  const [processPanel, setProcessPanel] = useState<'process' | null>(() => activityOpen ? 'process' : null)
  const activePanel = detail.selected?.messageId === id ? detail.selected.panel : processPanel
  const resultOpen = activePanel === 'result'
  const selectPanel = (panel: 'process' | 'result' | 'evidence' | null) => {
    if (activityRef.current) activityRef.current.open = panel === 'process'
    setActivityOpen(panel === 'process')
    setProcessPanel(panel === 'process' ? 'process' : null)
    if (panel === 'result' || panel === 'evidence') detail.select({messageId:id, panel})
    else detail.select(undefined)
  }
  const togglePanel = (panel: 'process' | 'result' | 'evidence') => selectPanel(activePanel === panel ? null : panel)
  const [pendingResultId, setPendingResultId] = useState<string | null>(null)
  const terminalWithoutText = role === 'assistant' && !hasText && status?.type !== 'running'
  const toggleActivity = () => togglePanel('process')
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
  const completedAnswer = !terminalNotice && hasText && role === 'assistant' && status?.type === 'complete'
  return <MessagePrimitive.Root data-message-id={id} data-attempt-id={attemptId} data-run-phase={role==='assistant'?(status?.type==='running'?'running':typeof custom?.terminalPhase==='string'?custom.terminalPhase:undefined):undefined} data-run-duration-ms={role==='assistant'?durationMs:undefined} data-run-started-at={role==='assistant'?startedAt:undefined} tabIndex={-1} aria-label={role === 'user' ? '用户指令' : '智能体回答'} className={`capstone-chat-message is-${role}${messageState ? ` is-${messageState}` : ''}`}>
    {role==='assistant'&&Boolean(custom?.initialThinking)&&<ThinkingProcess thinking={custom?.initialThinking as InitialThinking} storageKey={typeof custom?.stepStorageKey==='string'?custom.stepStorageKey:attemptId}/>}
    <div className="capstone-chat-body">
      {role==='user'&&Array.isArray(custom?.instructionFiles)&&<InstructionAttachments files={custom.instructionFiles as InstructionFile[]}/>}
      {!completedAnswer && <span className="capstone-chat-role">{role === 'user' ? '你' : author}</span>}
      {role === 'assistant' && typeof custom?.retainedResearchGoal === 'string' && <details className="capstone-task-research">
        <summary>研究记录中的目标</summary>
        <p>{custom.retainedResearchGoal}</p>
      </details>}
      {terminalNotice ? <>
        {typeof custom?.partialText === 'string' && custom.partialText && <MarkdownMessage>{custom.partialText}</MarkdownMessage>}
        <ThreadSystemNotice tone={custom?.terminalPhase === 'failed' ? 'error' : 'info'}><MarkdownMessage>{terminalNotice}</MarkdownMessage></ThreadSystemNotice>
      </> : completedAnswer ? <FoldableAnswer id={id} text={text} author={author} finishedAt={finishedAt} /> : hasText
        ? <MessagePrimitive.Parts components={{ Text: role === 'assistant' ? () => <MessagePartPrimitive.Text smooth={false} render={<MarkdownMessage />} /> : () => <MessagePartPrimitive.Text smooth={false} component="p" /> }} />
        : role === 'assistant' && <span className={`capstone-chat-placeholder${terminalWithoutText ? ' is-terminal' : ''}`}>{terminalWithoutText ? 'Attempt 已结束，暂无可显示的回答。' : '正在生成回答…'}</span>}
    </div>
    {completedAnswer && onOpenTaskResults && <div className="capstone-result-products">{taskResultCollections(attemptResultProjections, attemptId).map(collection => <button key={collection.id} type="button" className="capstone-result-product" onClick={() => onOpenTaskResults(collection)} aria-label={`打开${collection.title}`}><Activity aria-hidden="true" /><span><strong>{collection.title}</strong><small>本次指令 · {collection.results.length} 项分析结果</small></span><span aria-hidden="true">↗</span></button>)}</div>}
    {role==='assistant'&&onOpenNativeArtifact&&attemptFiles.length>0&&<InstructionFiles files={attemptFiles} onOpen={onOpenNativeArtifact}/>}
    {role === 'assistant' && <div ref={footerRef} className="capstone-chat-footer" onClickCapture={() => { if (footerRef.current) preserveControl(id, footerRef.current) }}>
      <RunDuration startedAt={startedAt} durationMs={durationMs} running={status?.type === 'running'} />
      {(hasText || terminalWithoutText) && <ChatActions answerLabel={instruction || text.slice(0, 100) || '本次回答'} onCloseEvidence={() => selectPanel(null)} networkSelected={selectedNetworkAttempt === attemptId} onShowNetwork={networkAttemptIds.includes(attemptId) && onShowNetwork ? () => onShowNetwork(attemptId) : undefined} role={role} text={text} evidenceRefs={evidenceState === 'available' ? evidenceRefs : []} evidenceState={evidenceState} resultAvailable={hasResults} resultOpen={resultOpen} onShowResult={() => togglePanel('result')} evidenceOpen={activePanel === 'evidence'} onShowEvidence={() => togglePanel('evidence')} contextId={contextId} selectionRevision={selectionRevision} toolCount={activities.length || toolCount} activityOpen={activityOpen} showActivity={showActivity} onShowActivity={toggleActivity} onRegenerate={retryable && onRegenerate ? () => onRegenerate(attemptId, instruction) : undefined}
        attemptId={attemptId} resultRefs={resultRefs} projections={attemptResultProjections} failures={failureResults} researchSnapshot={parseResearchSnapshot(custom?.researchSnapshot)} executions={(Array.isArray(custom?.toolExecutions) ? custom.toolExecutions : []) as ToolExecutionRecord[]}
        processAvailable={Boolean(startedAt) || (Array.isArray(custom?.modelRequests) && custom.modelRequests.length > 0) || Boolean(custom?.executionGraph) || (Array.isArray(custom?.taskSteps) && custom.taskSteps.length > 0) || Boolean(custom?.researchSnapshot) || failureResults.length > 0 || Boolean(readRecords)}
        onSelectResult={(resultId) => { selectPanel('result'); setPendingResultId(resultId) }} />}
    </div>}
    {role === 'assistant' && hasResults && resultOpen && <AnswerDetailSheet title="结果明细" answerLabel={instruction || text.slice(0, 100) || '本次回答'} onClose={() => selectPanel(null)}><ResultExplorer projections={attemptResultProjections} failures={failureResults}
      initialResultId={pendingResultId} onClose={() => { if (footerRef.current) preserveControl(id, footerRef.current); selectPanel(null) }} renderResult={(projection, tableId) =>
        <ResultProjectionCard projection={projection} tableId={tableId} onFocusElement={(value, elementId) => { if (onFocusElement?.(value, elementId) === true) selectPanel(null) }} />} /></AnswerDetailSheet>}
    {role === 'user' && hasText && <div className="capstone-instruction-meta">
      <ChatActions role={role} text={text} evidenceRefs={[]} toolCount={0} />
      {typeof custom?.modelId === 'string' && <span className="capstone-instruction-model">{instructionModelName(custom.modelId)}</span>}
      {typeof custom?.sentAt === 'string' && Number.isFinite(Date.parse(custom.sentAt)) && <InstructionTime value={custom.sentAt} />}
    </div>}
    {role === 'assistant' && (showActivity || status?.type === 'running' || hasAuxiliary) && <AttemptActivity activities={activities} modelRequests={Array.isArray(custom?.modelRequests) ? custom.modelRequests as ProcessModelCall[] : []} initialThinking={custom?.initialThinking as InitialThinking|undefined} nativeGraphFocus={custom?.nativeGraphFocus === 'tools' || custom?.nativeGraphFocus === 'tasks' ? custom.nativeGraphFocus : undefined} executionGraph={custom?.executionGraph as ExecutionGraph | undefined} diagnostics={Array.isArray(custom?.stepDiagnostics) ? custom.stepDiagnostics as TaskStepDiagnostic[] : []} branches={Array.isArray(custom?.researchBranches) ? custom.researchBranches as ResearchBranch[] : []} steps={Array.isArray(custom?.taskSteps) ? custom.taskSteps as TaskStep[] : []} stepStorageKey={typeof custom?.stepStorageKey === 'string' ? custom.stepStorageKey : attemptId} progress={Array.isArray(custom?.taskProgress) ? custom.taskProgress as TaskProgress[] : []} goal={typeof custom?.researchGoal === 'string' ? custom.researchGoal : undefined} phase={typeof custom?.terminalPhase === 'string' ? custom.terminalPhase : undefined} running={status?.type === 'running'} open={activityOpen} onOpenChange={(open) => { if (open) selectPanel('process'); else if (activePanel === 'process') selectPanel(null) }} startedAt={startedAt} durationMs={durationMs} detailsRef={activityRef} hasAuxiliary={hasAuxiliary} auxiliary={<>
      <AcceptedContextDetails value={custom?.acceptedContext} />
      {readRecords && <AttemptRecordPanel key={attemptId} attemptId={attemptId} read={readRecords} />}
      <ResearchEvidence snapshot={parseResearchSnapshot(custom?.researchSnapshot)} />
      {(failureResults.length > 0 || Array.isArray(custom?.toolExecutions) && custom.toolExecutions.length > 0) && <InferenceEvidencePanel title="执行记录" attemptId={attemptId} admitted={false} resultRefs={[]} evidenceRefs={[]} projections={[]} failures={failureResults} executions={(custom?.toolExecutions || []) as ToolExecutionRecord[]} />}
    </>} />}
  </MessagePrimitive.Root>
}

function instructionModelName(modelId: string): string {
  const known: Record<string, string> = { ieee39: 'IEEE-39', pypsa39: 'PyPSA-39', case24_ieee_rts: 'RTS-24' }
  return known[modelId] || modelId.split('/').at(-1) || modelId
}

function AcceptedContextDetails({ value }: { value: unknown }) {
  const context = value as { objects?: { object_id: string; display_name: string; version: string }[]; materials?: unknown[] }
  if (!Array.isArray(context?.objects) || context.objects.length === 0) return null
  return <details className="capstone-chat-activity capstone-accepted-context"><summary>本轮业务对象 · {context.objects.length} 个对象</summary>
    {context.objects.length ? <ul>{context.objects.map(object => <li key={object.object_id}>{object.display_name} · {object.version}</li>)}</ul> : <p>本轮未采用业务对象。</p>}
    <p>此处仅列业务对象，资料读取情况见本轮执行记录。</p>
  </details>
}

function InstructionTime({ value, completion = false }: { value: string; completion?: boolean }) {
  const date = new Date(value)
  const now = new Date()
  const clock = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
  const day = date.toLocaleDateString('zh-CN', { ...(date.getFullYear() !== now.getFullYear() ? { year: 'numeric' as const } : {}), month: '2-digit', day: '2-digit' })
  const full = date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZoneName: 'short' })
  return <time className={completion ? 'capstone-answer-time' : 'capstone-instruction-time'} dateTime={value} title={full} aria-label={`${completion ? '回答完成时间' : '指令发出时间'}：${full}`}>
    {date.toDateString() === now.toDateString() ? clock : `${day} ${clock}`}
  </time>
}

type AcceptedDraft = { text: string; commandId: string; submission?: InputSubmission }

function ComposerSurface({ initialRestoreError, productReferenceReader, disabled, isRunning, acceptedDraft, controls, contextTriggerRef, onRemoveMaterial, storageKey, inputDraft, onInputChange, inputCatalog, inputCatalogLoading, onRefreshInputCatalog, inputControlsDisabled, onBeforeInputChange, onBeforeSend, textOnly = false, placeholder, label = 'Thread 指令', sendLabel = '发送指令', initialText, onDraftChange, lockDraft = false, canCancel = true, cancelLabel = '停止生成', cancelDisabled = false }: { initialRestoreError?:string; productReferenceReader?:ProductReferenceReader;contextTriggerRef?:RefObject<HTMLButtonElement|null>;onRemoveMaterial?:(id:string)=>Promise<void>;canCancel?: boolean; cancelLabel?: string; cancelDisabled?: boolean; textOnly?: boolean; placeholder?: string; label?: string; sendLabel?: string; initialText?: string; onDraftChange?: (text: string) => void; lockDraft?: boolean; disabled: boolean; isRunning: boolean; acceptedDraft?: AcceptedDraft; controls?: ReactNode; storageKey?: string; inputDraft: InputDraft; onInputChange: (value: InputDraft) => void; inputCatalog?: InputCatalog; inputCatalogLoading?: boolean; onRefreshInputCatalog?: () => void; inputControlsDisabled?: boolean; onBeforeInputChange?: () => boolean; onBeforeSend?: () => boolean }) {
  const aui = useAui()
  const isEmpty = useAuiState((state) => state.composer.isEmpty)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [storageError,setStorageError]=useState('')
  const resolvedCommand = useRef<string | undefined>(undefined)
  const draftInitialized = useRef(!initialText&&!initialRestoreError)
  const text = useAuiState((state) => state.composer.text)
  useEffect(() => {
    if (!draftInitialized.current && !text) return
    draftInitialized.current = true
    try{writeDraft(storageKey, text);setStorageError('')}catch(error){setStorageError(error instanceof Error?error.message:'草稿暂时无法保存。')}
    onDraftChange?.(text)
  }, [text, storageKey, onDraftChange])
  useEffect(() => {
    if (acceptedDraft && resolvedCommand.current !== acceptedDraft.commandId) {
      resolvedCommand.current = acceptedDraft.commandId
      if (aui.composer.getState().text.trim() === acceptedDraft.text.trim()) {
        try {
          const current = buildInputSubmission(acceptedDraft.text.trim(), inputDraft)
          const {deep_research:currentDeep=false,...currentInput}=current
          const {deep_research:acceptedDeep=false,...acceptedInput}=acceptedDraft.submission??{}
          if (!acceptedDraft.submission || currentDeep===acceptedDeep&&JSON.stringify(currentInput)===JSON.stringify(acceptedInput)) {
            aui.composer.setText('')
            onInputChange({...emptyInputDraft(inputDraft.mode),llm_profile_id:inputDraft.llm_profile_id,...(inputDraft.material_refs===undefined?{}:{material_refs:inputDraft.material_refs})})
          }
        } catch { /* Keep an edited or incompatible next draft. */ }
      }
    }
  }, [aui, acceptedDraft, inputDraft, onInputChange])
  useEffect(() => {
    const input = inputRef.current
    if (input && !input.disabled) input.focus()
  }, [disabled, isRunning])
  const reserveSend = () => !observeCapacity(text.length,'input_text_chars','composer.submit') && !disabled && !isEmpty && text.length<=applicationCapacity('input_text_chars') && (textOnly || !inputDraftError(inputDraft, inputCatalog)) && onBeforeSend?.() !== false
  const surface = (inputTools?: ReactNode) => <ComposerPrimitive.Root className="capstone-composer-root" data-running={isRunning ? 'true' : 'false'} data-empty={isEmpty ? 'true' : 'false'}
    onClickCapture={event => { if (event.target instanceof Element && event.target.closest('.capstone-chat-send') && !reserveSend()) { event.preventDefault(); event.stopPropagation() } }}
    onKeyDownCapture={event => { if (event.target instanceof HTMLTextAreaElement && event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229 && !reserveSend()) { event.preventDefault(); event.stopPropagation() } }}>
    <ProductReferenceChips selections={inputDraft.context_product_refs||[]} read={productReferenceReader} disabled={lockDraft} onRemove={key=>onInputChange({...inputDraft,context_product_refs:(inputDraft.context_product_refs||[]).filter(item=>productRefKey(item.ref)!==key)})}/>
    {storageError&&<p role="alert">{storageError}</p>}
    <ComposerPrimitive.Input ref={inputRef} autoFocus aria-label={label} placeholder={textOnly ? '描述目标、已有资料与期望交付…' : isRunning ? '可先写下一条任务，完成后发送…' : disabled ? '可继续编辑草稿，当前操作完成后发送…' : placeholder ?? '描述你的任务，或输入 / 查看操作…'} disabled={lockDraft} submitMode="enter" />
    <div className="capstone-composer-footer"><div className="capstone-composer-toolbar" aria-label="输入工具栏">{inputTools}{controls}</div><div className="capstone-composer-actions">
      {isRunning && canCancel ? <ComposerPrimitive.Cancel className="capstone-chat-stop" aria-label={cancelLabel} title={cancelLabel} disabled={cancelDisabled} onMouseDown={(event) => event.preventDefault()}><Square aria-hidden="true" /></ComposerPrimitive.Cancel> : <ComposerPrimitive.Send className="capstone-chat-send" aria-label={sendLabel} title={sendLabel} disabled={disabled || isEmpty || (!textOnly && Boolean(inputDraftError(inputDraft, inputCatalog)))} onMouseDown={(event) => event.preventDefault()}><ArrowUp aria-hidden="true" /></ComposerPrimitive.Send>}
    </div></div>
  </ComposerPrimitive.Root>
  return textOnly ? surface() : <ThreadCommandMenu contextTriggerRef={contextTriggerRef} onRemoveMaterial={onRemoveMaterial} catalog={inputCatalog} loading={inputCatalogLoading} onRefresh={onRefreshInputCatalog} draft={inputDraft} onChange={onInputChange} disabled={inputControlsDisabled} onBeforeChange={onBeforeInputChange}>{surface}</ThreadCommandMenu>
}

function EmptyThreadState({ disabled }: { disabled: boolean }) {
  const aui = useAui()
  return <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><div className="capstone-chat-suggestions" aria-label="示例问题">
    {EMPTY_PROMPTS.map((prompt) => <button key={prompt} type="button" className="capstone-chat-suggestion" disabled={disabled} onClick={() => { aui.composer.setText(prompt); aui.composer.send() }}>{prompt}</button>)}
  </div></div>
}

export type CapstoneAssistantThreadProps = {
  /** Application projection of persisted messages; no synthetic runtime events. */
  productReferenceReader?:ProductReferenceReader
  requestedProductReference?:{selection:ContextProductRef;nonce:number}
  projectedMessages?: readonly ThreadMessageLike[]
  emptyState?: ReactNode
  runtimeStatus?: ReactNode
  connectionState?: string
  resultHistoryNotice?: string
  composerMode?: 'contextual' | 'text'
  composerLabel?: string
  composerPlaceholder?: string
  sendLabel?: string
  initialText?: string
  onDraftChange?: (text: string) => void
  lockDraft?: boolean
  canCancel?: boolean
  cancelLabel?: string
  cancelDisabled?: boolean
  readOnly?: boolean
  runtimeMode?: RuntimeMode
  onReadAttemptRecords?: AttemptRecordReader
  systemNotices?: readonly SystemNotice[]
  onSystemAction?: (action: 'reconnect' | 'resync') => void
  storageKey?: string
  hasOlderHistory?: boolean
  historyLoading?: boolean
  onLoadOlder?: () => Promise<void>
  historyAtLatest?: boolean
  onReturnLatest?: () => void
  instructionLocation?: { attemptId: string; nonce: number }
  events: readonly EventEnvelope[]
  disabled: boolean
  isRunning: boolean
  acceptedDraft?: AcceptedDraft
  activity: readonly (ChatActivity | string)[]
  onSend: (mode: SendMode, text: string, input?: InputSubmission) => Promise<void>
  inputCatalog?: InputCatalog
  inputCatalogLoading?: boolean
  onRefreshInputCatalog?: () => void
  inputControlsDisabled?: boolean
  onBeforeInputChange?: () => boolean
  onBeforeSend?: () => boolean
  onCancel: () => Promise<void>
  onRegenerate?: (attemptId: string, instruction?: string) => Promise<void>
  onFollowup?: (attemptId: string) => void
  canRerunCompleted?: boolean
  modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string }
  instructionModels?: readonly { contextId: string; modelId: string }[]
  composerControls?: (historyActions: ReactNode,inputActions:{addMaterial:(id:string)=>void}) => ReactNode
  contextTriggerRef?:RefObject<HTMLButtonElement|null>
  onRemoveMaterial?:(id:string)=>Promise<void>
  showActivity?: boolean
  caseExecution?: CaseExecutionSnapshot | null
  caseCatalog?: readonly ThreadCatalogCase[]
  caseStartDisabledReason?: string
  caseConnection?: ThreadTransportState | 'connecting'
  onCaseAction?: (actionId: CaseActionSnapshot['actionId']) => void
  onCaseStart?: (caseId: string, caseVersion: string) => void
  resultProjections?: readonly ResultProjection[]
  onOpenResultProduct?: (result: ResultProjection) => void
  onOpenTaskResults?: (product: TaskResultCollection) => void
  onOpenNativeArtifact?: (artifact:NativeArtifact)=>void
  nativeArtifactProjections?:readonly NativeArtifact[]
  onOpenAnswerDetail?: () => void
  onFocusElement?: (projection: ResultProjection, elementId: string) => boolean | void
  networkAttemptIds?: readonly string[]
  selectedNetworkAttempt?: string
  onShowNetwork?: (attemptId: string) => void
}

/** Assistant-ui is the presentation runtime; Capstone projection remains authoritative. */
type AnswerDetailSelection = { messageId: string; panel: 'result' | 'evidence' } | undefined
const AnswerDetailContext = createContext<{ selected: AnswerDetailSelection; select: (selection: AnswerDetailSelection) => void }>({selected:undefined, select:()=>{}})
const SystemActionContext = createContext<CapstoneAssistantThreadProps['onSystemAction']>(undefined)

export default function CapstoneAssistantThread({ nativeArtifactProjections, productReferenceReader,requestedProductReference,projectedMessages, emptyState, runtimeStatus, connectionState, resultHistoryNotice, composerMode = 'contextual', composerLabel, composerPlaceholder, sendLabel, initialText, onDraftChange, lockDraft, canCancel = true, cancelLabel, cancelDisabled, readOnly = false, onReadAttemptRecords, events, runtimeMode = 'capstone', systemNotices = [], onSystemAction, disabled, isRunning, acceptedDraft, activity, onSend, onCancel, onRegenerate, onFollowup, canRerunCompleted = !disabled, modelSummary, instructionModels, composerControls, contextTriggerRef, onRemoveMaterial, showActivity = true, caseExecution, caseCatalog = [], caseStartDisabledReason, caseConnection = 'live', onCaseAction, onCaseStart, resultProjections = [], onOpenResultProduct, onOpenTaskResults, onOpenNativeArtifact, onOpenAnswerDetail, onFocusElement, selectedNetworkAttempt, networkAttemptIds = [], onShowNetwork, storageKey, hasOlderHistory = false, historyLoading = false, onLoadOlder, historyAtLatest = true, onReturnLatest, instructionLocation, inputCatalog, inputCatalogLoading, onRefreshInputCatalog, inputControlsDisabled, onBeforeInputChange, onBeforeSend }: CapstoneAssistantThreadProps) {
  const [answerDetail, setAnswerDetail] = useState<AnswerDetailSelection>()
  const nativeArtifacts=useMemo(()=>[...new Map([...projectNativeArtifacts(events),...(nativeArtifactProjections||[])].map(file=>[`${file.thread_id}:${file.attempt_id}:${file.artifact_id}`,file])).values()],[events,nativeArtifactProjections])
  const [restoredInput]=useState(()=>{try{return {draft:readInputDraft(storageKey)||emptyInputDraft(runtimeMode),error:''}}catch(error){return {draft:emptyInputDraft(runtimeMode),error:error instanceof Error?error.message:'输入草稿无法恢复。'}}})
  const [inputDraft, setInputDraft] = useState<InputDraft>(restoredInput.draft)
  useEffect(()=>{
    const profile=inputCatalog?.llm_profiles?.default_profile_id
    if(profile)setInputDraft(current=>current.llm_profile_id===undefined?{...current,llm_profile_id:profile}:current)
  },[inputCatalog?.llm_profiles?.default_profile_id])
  const [productReferenceError,setProductReferenceError]=useState(restoredInput.error)
  useEffect(()=>{
    if(!requestedProductReference)return
    try{
      const selection=parseContextProductRefs([requestedProductReference.selection])[0]
      const items=inputDraft.context_product_refs||[]
      const exists=items.some(item=>productRefKey(item.ref)===productRefKey(selection.ref))
      if(items.length>=applicationCapacity('product_reference_count')&&!exists){setProductReferenceError(`本轮最多引用 ${applicationCapacity('product_reference_count')} 项成果，请先移除一项。`);return}
      setProductReferenceError('')
      setInputDraft(current=>({...current,context_product_refs:exists?items.map(item=>productRefKey(item.ref)===productRefKey(selection.ref)?selection:item):[...items,selection]}))
    }catch{setProductReferenceError('成果引用无效，请重新选择。')}
  },[requestedProductReference?.nonce])
  const activeInput = { ...inputDraft, llm_profile_id:inputDraft.llm_profile_id??inputCatalog?.llm_profiles?.default_profile_id, mode: runtimeMode,deep_research:runtimeMode==='capstone'?inputDraft.deep_research??false:undefined }
  useEffect(() => { if(restoredInput.error&&inputDraft===restoredInput.draft)return; try{writeInputDraft(storageKey, activeInput)}catch(error){setProductReferenceError(error instanceof Error?error.message:'输入草稿暂时无法保存。')} }, [storageKey, inputDraft, runtimeMode,activeInput.llm_profile_id])
  const [submittingThinking,setSubmittingThinking]=useState<{id:string;text:string;afterSeq:number;at:string}>()
  const submitSequence=useRef(0)
  const allMessages = useMemo(() => {
    const rows=bindInstructionAttachments(projectedMessages ? [...projectedMessages] : projectSystemNotices(projectAssistantMessages(events, instructionModels), events, systemNotices, historyAtLatest),inputCatalog?.stored_resources||[])
    if(!submittingThinking||events.some(event=>event.eventType==='command_accepted'&&event.eventSeq>submittingThinking.afterSeq&&payloadText(event,true)===submittingThinking.text))return rows
    return [...rows,{id:submittingThinking.id,role:'assistant' as const,content:'',status:{type:'running' as const},metadata:{custom:{source:'optimistic-submit',initialThinking:{text:'',phase:'queued',handedOff:false,startedAt:submittingThinking.at} satisfies InitialThinking,stepStorageKey:submittingThinking.id}}}]
  }, [projectedMessages, events, instructionModels, systemNotices, historyAtLatest,submittingThinking,inputCatalog?.stored_resources])
  const firstPublicEventSeq = useMemo(() => events.reduce((first, event) => event.visibility === 'public' ? Math.min(first, event.eventSeq) : first, Number.POSITIVE_INFINITY), [events])
  const [foldState, setFoldState] = useSessionViewState<{ thread: string | undefined; ids: string[] }>('conversation.folds',{ thread: storageKey, ids: [] })
  const collapsedAnswers = new Set(foldState.thread === storageKey ? foldState.ids : [])
  const viewportRef = useRef<HTMLDivElement>(null)
  const savedPosition=useHasSavedSessionPosition('conversation')
  const [restoringSessionPosition,setRestoringSessionPosition]=useState(savedPosition)
  useLayoutEffect(()=>{if(savedPosition)setRestoringSessionPosition(true)},[savedPosition])
  const alignedInstruction=useSessionViewRef<string|undefined>('conversation.aligned-instruction',undefined)
  const latestInstructionId = allMessages.filter(message => message.role === 'user').at(-1)?.id
  useLayoutEffect(() => {
    if (!isRunning||alignedInstruction.current===latestInstructionId) return
    const viewport = viewportRef.current
    if (!viewport) return
    let aligned = false
    let reserved = false
    let frame = 0
    const align = () => {
      if (aligned) return
      const instruction = Array.from(viewport.querySelectorAll<HTMLElement>('.is-user[data-message-id]'))
        .find(node => node.dataset.messageId === latestInstructionId)
      if (!instruction || viewport.clientHeight === 0) return
      const view = viewport.getBoundingClientRect()
      const question = instruction.getBoundingClientRect()
      const desired = Math.max(0, viewport.scrollTop + question.top - view.top - 8)
      const missing = desired - Math.max(0, viewport.scrollHeight - viewport.clientHeight)
      if (missing > 1 && !reserved) {
        reserved = true
        setReadingTailSpace(space => space + missing)
        schedule()
        return
      }
      const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      if (typeof viewport.scrollTo === 'function' && !reducedMotion) viewport.scrollTo({ top: desired, behavior: 'smooth' })
      else viewport.scrollTop = desired
      aligned = true
      alignedInstruction.current=latestInstructionId
      observer.disconnect()
    }
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(align) }
    const observer = new MutationObserver(schedule)
    observer.observe(viewport, { childList: true, subtree: true })
    schedule()
    return () => { observer.disconnect(); cancelAnimationFrame(frame) }
  }, [isRunning, latestInstructionId])
  const [readingLayoutChanging, setReadingLayoutChanging] = useState(false)
  const [readingTailSpace, setReadingTailSpace] = useSessionViewState('conversation.tail-space',0)
  type ReadingAnchor = { id: string; top: number; control?: HTMLButtonElement; instructionId?: string; element?: HTMLElement }
  const scrollAnchor = useRef<ReadingAnchor | null>(null)
  const historyAnchor = useRef<ReadingAnchor | null>(null)
  const historyLoadToken = useRef(0)
  const [historyAnchorRevision, setHistoryAnchorRevision] = useState(0)
  const pendingHistoryAnchor = useRef<{ token: number; baselineFirstEventSeq: number; settled: boolean } | null>(null)
  const returnLatestScrollPending = useRef(false)
  const returnLatestScrollToken = useRef(0)
  function scrollViewportToLatest() {
    const viewport = viewportRef.current
    if (viewport) viewport.scrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight)
  }
  function requestLatestScroll() {
    returnLatestScrollPending.current = true
    returnLatestScrollToken.current += 1
    scrollAnchor.current = null
    historyAnchor.current = null
    pendingHistoryAnchor.current = null
  }
  function cancelLatestScrollIntent() {
    if (!returnLatestScrollPending.current) return
    returnLatestScrollPending.current = false
    returnLatestScrollToken.current += 1
  }
  function cancelLatestScrollIntentForKey(event: ReactKeyboardEvent) {
    if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) cancelLatestScrollIntent()
  }
  function captureScrollAnchor(id: string, control: HTMLButtonElement) {
    const viewport = viewportRef.current
    if (!viewport) return
    const nodes = Array.from(viewport.querySelectorAll<HTMLElement>('[data-message-id]'))
    setReadingLayoutChanging(true)
    const instructionId = allMessages.find((message) => message.id === id)?.metadata?.custom?.instructionMessageId
    const instructionIndex = typeof instructionId === 'string' ? allMessages.findIndex((message) => message.id === instructionId) : -1
    scrollAnchor.current = { id, top: control.getBoundingClientRect().top, control,
      instructionId: instructionIndex >= 0 ? instructionId as string : undefined }
  }
  function preserveControl(id: string, element: HTMLElement) {
    if (!viewportRef.current) return
    scrollAnchor.current = { id, top: element.getBoundingClientRect().top, element }
    historyAnchor.current = null
    setReadingLayoutChanging(true)
  }
  function captureHistoryAnchor(options: { revealInstructionForAnswer?: boolean; preferAnswerToggle?: boolean; reusePrevious?: boolean } = {}) {
    const viewport = viewportRef.current
    if (!viewport) return
    const view = viewport.getBoundingClientRect()
    const nodes = Array.from(viewport.querySelectorAll<HTMLElement>('[data-message-id]'))
    const { revealInstructionForAnswer = true, preferAnswerToggle = true, reusePrevious = true } = options
    const previous = historyAnchor.current
    const previousNode = reusePrevious
      ? previous?.element?.isConnected ? previous.element : nodes.find((node) => node.dataset.messageId === previous?.id)
      : undefined
    // Reuse the reading subject through consecutive actions. Re-select only
    // after the user moves it, or its message leaves the rendered window.
    if (previous && previousNode && Math.abs(previousNode.getBoundingClientRect().top - previous.top) < 2) {
      scrollAnchor.current = previous
    } else {
      const visible = nodes.filter((node) => { const rect = node.getBoundingClientRect(); return rect.bottom > view.top && rect.top < view.bottom })
      const question = visible.find((node) => node.classList.contains('is-user'))
      const message = question || visible[0]
      if (!message?.dataset.messageId) return
      const instructionId = allMessages.find((item) => item.id === message.dataset.messageId)?.metadata?.custom?.instructionMessageId
      const instructionIndex = typeof instructionId === 'string' ? allMessages.findIndex((item) => item.id === instructionId) : -1
      const instruction = nodes.find((node) => node.dataset.messageId === instructionId)
      // During fold actions, a reply may collapse away from the current view.
      // Restore its instruction once; paging keeps the visible message itself.
      const revealInstruction = revealInstructionForAnswer && !question && instructionIndex >= 0
      const element = !question && !revealInstruction && preferAnswerToggle ? message.querySelector<HTMLElement>('.capstone-answer-toggle') ?? undefined : undefined
      const anchor = { id: revealInstruction ? instructionId as string : message.dataset.messageId,
        top: revealInstruction ? view.top + 8 : (element || message).getBoundingClientRect().top, element }
      scrollAnchor.current = anchor
      historyAnchor.current = anchor
    }
    setReadingLayoutChanging(true)
  }
  function restoreReadingAnchor(id?: string) {
    const anchor = scrollAnchor.current
    if (!anchor || (id && anchor.id !== id)) return
    const viewport = viewportRef.current
    const nodes = Array.from(viewport?.querySelectorAll<HTMLElement>('[data-message-id]') || [])
    const answer = nodes.find((item) => item.dataset.messageId === anchor.id)
    const control = anchor.control?.isConnected ? anchor.control : anchor.control ? answer?.querySelector<HTMLButtonElement>('.capstone-answer-toggle') : undefined
    const node = control || (anchor.element?.isConnected ? anchor.element : answer)
    if (anchor && node && viewport) {
      let desired = viewport.scrollTop + node.getBoundingClientRect().top - anchor.top
      const instruction = nodes.find((item) => item.dataset.messageId === anchor.instructionId)
      if (instruction) {
        const view = viewport.getBoundingClientRect()
        const question = instruction.getBoundingClientRect()
        const upper = viewport.scrollTop + question.top - view.top - 8
        const lower = viewport.scrollTop + question.bottom - view.bottom + 8
        // Keep both ends of the associated instruction in view. An unusually
        // tall instruction falls back to its start instead of another message.
        desired = lower <= upper ? Math.min(upper, Math.max(lower, desired)) : upper
      }
      const maximum = viewport.scrollHeight - viewport.clientHeight
      // Collapsing the final reply can remove the scroll range required to
      // keep its control in place. Preserve only the missing reading space.
      if (desired > maximum + 1) setReadingTailSpace(readingTailSpace + desired - maximum)
      else viewport.scrollTop = desired
      control?.focus({ preventScroll: true })
    }
  }
  useLayoutEffect(() => restoreReadingAnchor(), [foldState, readingTailSpace])
  useLayoutEffect(() => {
    const pending = pendingHistoryAnchor.current
    if (pending?.settled && firstPublicEventSeq < pending.baselineFirstEventSeq) {
      setReadingLayoutChanging(true)
    }
  }, [firstPublicEventSeq, historyAnchorRevision])
  useEffect(() => {
    if (!readingLayoutChanging) return
    // Assistant-ui follows height changes while at the latest reply. Pause that
    // behavior until the stable control and content resize settle.
    let second: number | undefined
    const first = window.requestAnimationFrame(() => {
      restoreReadingAnchor()
      second = window.requestAnimationFrame(() => {
        restoreReadingAnchor()
        const anchor = scrollAnchor.current
        if (anchor && historyAnchor.current === anchor) {
          const nodes = Array.from(viewportRef.current?.querySelectorAll<HTMLElement>('[data-message-id]') || [])
          const node = anchor.element?.isConnected ? anchor.element : nodes.find((item) => item.dataset.messageId === anchor.id)
          // At a scroll boundary, the browser rounds the requested position.
          // Hold its actual landing point during the next history action.
          if (node) historyAnchor.current = { ...anchor, top: node.getBoundingClientRect().top }
        }
        const pending = pendingHistoryAnchor.current
        const waitingForHistory = pending && (!pending.settled || firstPublicEventSeq >= pending.baselineFirstEventSeq)
        if (pending && !waitingForHistory) pendingHistoryAnchor.current = null
        if (!waitingForHistory) scrollAnchor.current = null
        setReadingLayoutChanging(false)
      })
    })
    return () => { window.cancelAnimationFrame(first); if (second !== undefined) window.cancelAnimationFrame(second) }
  }, [readingLayoutChanging, foldState, readingTailSpace, firstPublicEventSeq])
  const previousStorageKey=useRef(storageKey)
  useEffect(() => {
    if(previousStorageKey.current===storageKey)return
    previousStorageKey.current=storageKey
    setFoldState((state) => state.thread === storageKey ? state : { thread: storageKey, ids: [] })
    setReadingTailSpace(0)
    historyAnchor.current = null
  }, [storageKey])
  function toggleAnswer(id: string, control: HTMLButtonElement) {
    historyAnchor.current = null
    control.focus({ preventScroll: true })
    captureScrollAnchor(id, control)
    setReadingTailSpace(0)
    setFoldState((state) => {
      const ids = new Set(state.thread === storageKey ? state.ids : [])
      if (ids.has(id)) ids.delete(id); else ids.add(id)
      return { thread: storageKey, ids:[...ids] }
    })
  }
  const completedAnswers = allMessages.filter((message) => message.role === 'assistant' && message.status?.type === 'complete' && !message.metadata?.custom?.systemNotice)
  function organizeHistory(fold: boolean) {
    if (!completedAnswers.some((message) => message.id && collapsedAnswers.has(message.id) !== fold)) return
    captureHistoryAnchor()
    setReadingTailSpace(0)
    const snapshot = completedAnswers.flatMap((message) => message.id ? [message.id] : [])
    setFoldState((state) => {
      const ids = new Set(state.thread === storageKey ? state.ids : [])
      for (const id of snapshot) { if (fold) ids.add(id); else ids.delete(id) }
      return { thread: storageKey, ids:[...ids] }
    })
  }
  const messages = allMessages
  const [locatingInstruction, setLocatingInstruction] = useState(false)
  const currentLocation = useRef(instructionLocation)
  currentLocation.current = instructionLocation
  const handledLocation = useRef<CapstoneAssistantThreadProps['instructionLocation']>(undefined)
  const locationHighlight = useRef<{ node: HTMLElement; timer: number }>(undefined)
  useEffect(() => () => {
    if (locationHighlight.current) { window.clearTimeout(locationHighlight.current.timer); locationHighlight.current.node.classList.remove('is-located-instruction') }
  }, [])
  useLayoutEffect(() => {
    if (!instructionLocation) { setLocatingInstruction(false); return }
    if (handledLocation.current === instructionLocation) return
    const index = allMessages.findIndex(message => message.role === 'user' && message.metadata?.custom?.attemptId === instructionLocation.attemptId)
    if (index < 0) return
    setLocatingInstruction(true)
    const viewport = viewportRef.current
    const instruction = Array.from(viewport?.querySelectorAll<HTMLElement>('[data-message-id]') || [])
      .find(node => node.dataset.messageId === allMessages[index].id)
    if (!instruction) {
      setLocatingInstruction(false)
      return
    }
    if (!viewport) return
    handledLocation.current = instructionLocation
    if (locationHighlight.current) { window.clearTimeout(locationHighlight.current.timer); locationHighlight.current.node.classList.remove('is-located-instruction') }
    const initialView = viewport.getBoundingClientRect()
    const initialQuestion = instruction.getBoundingClientRect()
    const needsAlignment = initialQuestion.top < Math.max(0, initialView.top) || initialQuestion.bottom > Math.min(window.innerHeight, initialView.bottom)
    if (needsAlignment) {
      const desired = viewport.scrollTop + initialQuestion.top - initialView.top - 16
      const missingSpace = desired - Math.max(0, viewport.scrollHeight - viewport.clientHeight)
      if (missingSpace > 0) setReadingTailSpace(space => space + missingSpace)
    }
    const locate = () => {
      if (currentLocation.current !== instructionLocation || !instruction.isConnected) return
      const view = viewport.getBoundingClientRect()
      const question = instruction.getBoundingClientRect()
      if (needsAlignment) {
        viewport.scrollTop += question.top - view.top - 16
      }
      const visible = instruction.getBoundingClientRect()
      if (visible.top < 0 || visible.bottom > window.innerHeight) instruction.scrollIntoView?.({ block: 'start' })
    }
    locate()
    window.requestAnimationFrame(() => {
      if (currentLocation.current !== instructionLocation) return
      locate()
      window.requestAnimationFrame(() => {
        if (currentLocation.current !== instructionLocation) return
        locate()
        setLocatingInstruction(false)
      })
    })
    instruction.classList.add('is-located-instruction')
    const timer = window.setTimeout(() => instruction.classList.remove('is-located-instruction'), 1200)
    locationHighlight.current = { node: instruction, timer }
  }, [instructionLocation, allMessages])
  const [historyError, setHistoryError] = useState<string | null>(null)
  async function olderMessages() {
    setHistoryError(null)
    if (!onLoadOlder || historyLoading) return
    captureHistoryAnchor({ revealInstructionForAnswer: false, preferAnswerToggle: false, reusePrevious: false })
    const token = scrollAnchor.current ? historyLoadToken.current + 1 : undefined
    if (token !== undefined) {
      historyLoadToken.current = token
      pendingHistoryAnchor.current = { token, baselineFirstEventSeq: firstPublicEventSeq, settled: false }
    }
    try {
      await onLoadOlder()
      if (token !== undefined && pendingHistoryAnchor.current?.token === token) {
        pendingHistoryAnchor.current = { ...pendingHistoryAnchor.current, settled: true }
        setHistoryAnchorRevision((value) => value + 1)
      }
    } catch (cause) {
      if (token !== undefined && pendingHistoryAnchor.current?.token === token) pendingHistoryAnchor.current = null
      setHistoryError(cause instanceof Error ? cause.message : '更早消息暂不可用')
    }
  }
  function returnToLatest() {
    setRestoringSessionPosition(false)
    setHistoryError(null)
    requestLatestScroll()
    if (!historyAtLatest) {
      onReturnLatest?.()
      return
    }
    scrollViewportToLatest()
    returnLatestScrollPending.current = false
  }
  useLayoutEffect(() => {
    if (!historyAtLatest || !returnLatestScrollPending.current) return
    const token = returnLatestScrollToken.current
    let second: number | undefined
    const restore = () => {
      if (!returnLatestScrollPending.current || returnLatestScrollToken.current !== token) return false
      scrollViewportToLatest()
      return true
    }
    restore()
    const first = window.requestAnimationFrame(() => {
      if (!restore()) return
      second = window.requestAnimationFrame(() => {
        if (restore()) returnLatestScrollPending.current = false
      })
    })
    return () => { window.cancelAnimationFrame(first); if (second !== undefined) window.cancelAnimationFrame(second) }
  }, [historyAtLatest])
  const [restoredText] = useState(() => {try{return {text:initialText??readDraft(storageKey),error:''}}catch(error){return {text:'',error:error instanceof Error?error.message:'指令草稿无法恢复。'}}})
  const initialDraft=restoredText.text
  const normalizedActivity = activity.map((item) => typeof item === 'string' ? { id: item, label: item, source: 'capstone-harness', status: 'completed' as const } : item)
  const legacyActivity = activity.some((item) => typeof item === 'string')
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    convertMessage: (message) => message,
    isSendDisabled: disabled || (composerMode !== 'text' && Boolean(inputDraftError(activeInput, inputCatalog))),
    isRunning,
    onNew: async (message) => {
      const text = messageText(message)
      if (text.trim()) {
        const submissionId=`assistant-submitting-${++submitSequence.current}`
        setSubmittingThinking({id:submissionId,text:text.trim(),afterSeq:Math.max(0,...events.map(event=>event.eventSeq)),at:new Date().toISOString()})
        try {
        if (composerMode === 'text') {
          await onSend('automatic', text.trim())
          returnToLatest()
          return
        }
        const sent = inputDraft
        const metadata = buildInputSubmission(text.trim(), activeInput)
        if(runtimeMode==='capstone'||metadata.llm_profile_id!==undefined||inputDraft.skill||inputDraft.literal||inputDraft.context.include_refs.length||inputDraft.context.exclude_refs.length||inputDraft.material_refs!==undefined||inputDraft.context_product_refs!==undefined)await onSend('automatic', text.trim(), metadata)
        else await onSend('automatic',text.trim())
        setInputDraft(current => current === sent ? {...emptyInputDraft(runtimeMode),llm_profile_id:metadata.llm_profile_id,...(sent.material_refs===undefined?{}:{material_refs:sent.material_refs})} : current)
        returnToLatest()
        } finally { setSubmittingThinking(current=>current?.id===submissionId?undefined:current) }
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
    <AnswerDetailContext.Provider value={{selected:answerDetail, select:selection=>{setAnswerDetail(selection);if(selection)onOpenAnswerDetail?.()}}}>
    <SystemActionContext.Provider value={onSystemAction}>
    <AttemptRecordsContext.Provider value={onReadAttemptRecords}>
    <AnswerReadingContext.Provider value={{ collapsed: collapsedAnswers, toggle: toggleAnswer, restoreAnchor: restoreReadingAnchor, preserveControl }}>
    <ChatMessageContext.Provider value={{ selectedNetworkAttempt, networkAttemptIds, onShowNetwork, onRegenerate: isRunning ? undefined : onRegenerate, onFollowup: isRunning ? undefined : onFollowup, canRerunCompleted, modelSummary, showActivity, resultProjections, onFocusElement, onOpenResultProduct, onOpenTaskResults, nativeArtifacts, onOpenNativeArtifact }}>
    <div className="capstone-assistant-thread" data-testid="assistant-ui-chat" onClickCapture={event => {
      const summary = event.target instanceof Element ? event.target.closest('summary') : null
      const message = summary?.closest<HTMLElement>('[data-message-id]')
      if (summary instanceof HTMLElement && message?.dataset.messageId) {
        preserveControl(message.dataset.messageId, summary)
      }
    }}>
      <div className="capstone-assistant-runtime-label">{runtimeMode === 'capstone'&&<span role="img" aria-label={connectionState==='live'?'会话实时连接已连接':'会话实时连接未连接'} title={connectionState==='live'?'会话实时连接已连接':'会话实时连接未连接'} className={`assistant-live-dot${connectionState==='live'?' is-live':''}`}/>}{runtimeMode === 'pi_reference' ? 'Pi' : 'CAPSTONE'}{runtimeMode === 'capstone' && <span>· HARNESS</span>}<small>{runtimeStatus??'实时响应'}</small></div>
      <ThreadPrimitive.Root className="capstone-chat-runtime">
        {(hasOlderHistory || !historyAtLatest || historyError) && <div className="capstone-chat-history-controls" aria-label="消息历史">
          {hasOlderHistory && <button type="button" disabled={historyLoading} onClick={() => void olderMessages()}>{historyLoading ? '正在加载…' : '查看之前的对话'}</button>}
          {!historyAtLatest && <button type="button" onClick={returnToLatest}>返回最新对话</button>}
          {historyError && <span role="alert">{historyError}</span>}
        </div>}
        {!caseExecution && caseCatalog.length > 0 && <><ThreadCasePicker cases={caseCatalog} disabled={disabled || Boolean(caseStartDisabledReason) || caseConnection === 'resync_required'} onStart={(caseId, caseVersion) => onCaseStart?.(caseId, caseVersion)} />{caseStartDisabledReason && <small>{caseStartDisabledReason}</small>}</>}
        {caseExecution && <ThreadCaseProgress execution={caseExecution} connection={caseConnection} onAction={(actionId) => onCaseAction?.(actionId)} />}
        {typeof ResizeObserver === 'undefined' ? <div ref={viewportRef} data-reading-key="conversation" className="capstone-chat-viewport" onWheel={cancelLatestScrollIntent} onTouchStart={cancelLatestScrollIntent} onKeyDown={cancelLatestScrollIntentForKey}>
          {messages.length === 0 && (emptyState ?? <EmptyThreadState disabled={disabled} />)}
          <ThreadPrimitive.Messages components={{ Message: ThreadChatMessage }} />
          {readingTailSpace > 0 && <div aria-hidden="true" style={{ height: readingTailSpace, flexShrink: 0 }} />}
        </div> : <ThreadPrimitive.Viewport ref={viewportRef} data-reading-key="conversation" className="capstone-chat-viewport" autoScroll={!restoringSessionPosition && !isRunning && !readingLayoutChanging && !locatingInstruction} scrollToBottomOnInitialize={false} scrollToBottomOnRunStart={false} onWheel={cancelLatestScrollIntent} onTouchStart={cancelLatestScrollIntent} onKeyDown={cancelLatestScrollIntentForKey}>
          {messages.length === 0 && (emptyState ?? <EmptyThreadState disabled={disabled} />)}
          <ThreadPrimitive.Messages components={{ Message: ThreadChatMessage }} />
          {readingTailSpace > 0 && <div aria-hidden="true" style={{ height: readingTailSpace, flexShrink: 0 }} />}
        </ThreadPrimitive.Viewport>}
        {resultHistoryNotice&&<p role="status">{resultHistoryNotice}</p>}
        <InstructionMarkers viewportRef={viewportRef} />
        {legacyActivity && normalizedActivity.length > 0 && <LegacyActivity activities={normalizedActivity} running={isRunning} />}
        {!readOnly && <div className="capstone-chat-composer">
          {(productReferenceError||restoredText.error)&&<p role="alert">{productReferenceError||restoredText.error}</p>}
          <ComposerSurface initialRestoreError={restoredText.error} productReferenceReader={productReferenceReader} contextTriggerRef={contextTriggerRef} onRemoveMaterial={onRemoveMaterial} cancelLabel={cancelLabel} cancelDisabled={cancelDisabled} canCancel={canCancel} textOnly={composerMode === 'text'} label={composerLabel} placeholder={composerPlaceholder} sendLabel={sendLabel} initialText={initialText} onDraftChange={onDraftChange} lockDraft={lockDraft} disabled={disabled} isRunning={isRunning} acceptedDraft={acceptedDraft} controls={composerControls ? composerControls(<HistoryAnswerActions disabled={completedAnswers.length === 0} onFold={() => organizeHistory(true)} onUnfold={() => organizeHistory(false)} />,{addMaterial:id=>setInputDraft(current=>current.material_refs===undefined?current:{...current,material_refs:[...new Set([...current.material_refs,id])]})}) : <ThreadSettingsMenu><HistoryAnswerActions disabled={completedAnswers.length === 0} onFold={() => organizeHistory(true)} onUnfold={() => organizeHistory(false)} /></ThreadSettingsMenu>} storageKey={storageKey} inputDraft={activeInput} onInputChange={setInputDraft} inputCatalog={inputCatalog} inputCatalogLoading={inputCatalogLoading} onRefreshInputCatalog={onRefreshInputCatalog} inputControlsDisabled={inputControlsDisabled} onBeforeInputChange={onBeforeInputChange} onBeforeSend={onBeforeSend} />
        </div>}
      </ThreadPrimitive.Root>
    </div>
    </ChatMessageContext.Provider>
    </AnswerReadingContext.Provider>
    </AttemptRecordsContext.Provider>
    </SystemActionContext.Provider>
    </AnswerDetailContext.Provider>
  </AssistantRuntimeProvider>
}
