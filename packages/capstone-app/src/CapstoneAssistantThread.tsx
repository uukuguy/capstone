import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
import { Activity, Check, Copy, FileCheck2, ListTree, MoreHorizontal, Pencil, RotateCcw, SendHorizontal, Square, ThumbsDown, ThumbsUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { EventEnvelope } from './threadProtocol'

type SendMode = 'automatic' | 'ordinary' | 'professional'

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
      : event.eventType === 'tool_failed' ? 'failed' : event.eventType === 'tool_cancelled' ? 'cancelled' : 'completed'
    const startedAt = previous?.startedAt || (event.eventType === 'tool_started' ? event.occurredAt : undefined)
    grouped.set(id, {
      id,
      label: TOOL_LABELS[toolName(event)] || toolName(event).replaceAll('_', ' '),
      source: activitySource(event),
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

function durationBetween(startedAt: string | undefined, finishedAt: string | undefined): number | undefined {
  if (!startedAt || !finishedAt) return undefined
  const start = Date.parse(startedAt)
  const finish = Date.parse(finishedAt)
  if (!Number.isFinite(start) || !Number.isFinite(finish)) return undefined
  return Math.max(0, finish - start)
}

export function projectAssistantMessages(events: readonly EventEnvelope[]): ThreadMessageLike[] {
  const messages: ThreadMessageLike[] = []
  const assistantByAttempt = new Map<string, ThreadMessageLike & { content: string }>()
  const instructionByAttempt = new Map<string, { text: string; mode: SendMode }>()
  const startedAtByAttempt = new Map<string, string>()
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
    if (event.eventType === 'command_accepted' && (event.payload.kind === 'send_auto' || event.payload.kind === 'send_ordinary' || event.payload.kind === 'send_professional')) {
      const text = payloadText(event, true)
      if (text) {
        const key = event.attemptId || event.turnId
        if (key) instructionByAttempt.set(key, { text, mode: commandMode(event) })
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
      if (!message && key) message = ensureAssistant(key, key ? startedAtByAttempt.get(key) : undefined)
      if (message && !message.content && answer) {
        message.content = answer
      }
      if (message) {
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
            modelContextId: event.modelContextId,
            selectionRevision: event.selectionRevision,
            instruction: key ? instructionByAttempt.get(key)?.text : undefined,
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
      metadata: { custom: { attemptId: key, source: 'capstone-harness', toolCount: events.filter((candidate) => candidate.attemptId === key && candidate.eventType.startsWith('tool_')).length, instruction: instructionByAttempt.get(key)?.text, modelContextId: event.modelContextId, selectionRevision: event.selectionRevision, startedAt: startedAtByAttempt.get(key), finishedAt: event.occurredAt, durationMs: durationBetween(startedAtByAttempt.get(key), event.occurredAt) } },
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

function IconAction({ label, onClick, expanded, children }: { label: string; onClick?: () => void; expanded?: boolean; children: ReactNode }) {
  return <button type="button" className="capstone-chat-action" aria-label={label} title={label} onClick={onClick} {...(expanded === undefined ? {} : { 'aria-expanded': expanded })}>{children}</button>
}

function ChatActions({ role, text, evidenceRefs, toolCount, onRegenerate, onShowActivity, onEditInstruction, activityOpen }: { role: string; text: string; evidenceRefs: string[]; toolCount: number; onRegenerate?: () => Promise<void>; onShowActivity?: () => void; onEditInstruction?: (text: string) => void; activityOpen?: boolean }) {
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
    {onRegenerate && <IconAction label="重新运行回答" onClick={() => void onRegenerate()}><RotateCcw /></IconAction>}
    {evidenceRefs.length > 0 && <IconAction label="查看证据" expanded={showEvidence} onClick={() => setShowEvidence((value) => !value)}><FileCheck2 /></IconAction>}
    {toolCount > 0 && <IconAction label="查看运行过程" expanded={activityOpen} onClick={onShowActivity}><ListTree /></IconAction>}
    <IconAction label="回答有帮助"><ThumbsUp /></IconAction>
    <IconAction label="回答需改进"><ThumbsDown /></IconAction>
    <IconAction label="更多回答操作"><MoreHorizontal /></IconAction>
  </div>
  {showEvidence && <div className="capstone-chat-evidence" aria-label="当前运行证据"><strong><FileCheck2 /> 当前运行证据</strong><div>{evidenceRefs.map((ref) => <code key={ref}>{ref}</code>)}</div></div>}
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

function AttemptActivity({ activities, running, open, startedAt, durationMs, detailsRef }: { activities: ChatActivity[]; running: boolean; open: boolean; startedAt?: string; durationMs?: number; detailsRef: React.RefObject<HTMLDetailsElement | null> }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])
  const liveDuration = startedAt ? durationBetween(startedAt, new Date(now).toISOString()) : undefined
  const elapsed = running ? liveDuration : durationMs
  if (activities.length === 0) return null
  return <details ref={detailsRef} className="capstone-chat-activity capstone-chat-activity-attached" open={open}>
    <summary><Activity aria-hidden="true" /><span>{running ? '正在执行' : '已完成'} {activities.length} 个步骤{elapsed === undefined ? '' : ` · ${running ? '运行中' : '运行'} ${formatDuration(elapsed)}`}</span><small>查看运行过程</small></summary>
    <div className="capstone-chat-activity-list">{activities.map((item) => <div key={item.id} className={`capstone-chat-activity-item is-${item.status}`}><span className="capstone-chat-activity-icon" aria-hidden="true" /> <span><strong>{item.label}</strong><small>{item.source}{item.durationMs === undefined ? '' : ` · ${formatDuration(item.durationMs)}`}</small></span></div>)}</div>
  </details>
}

function RunArtifacts({ resultRefs, evidenceRefs, admission, modelSummary }: { resultRefs: string[]; evidenceRefs: string[]; admission: unknown; modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string } }) {
  if (resultRefs.length === 0 && evidenceRefs.length === 0) return null
  const admitted = Boolean(admission && typeof admission === 'object' && 'status' in admission && (admission as { status?: unknown }).status === 'admitted')
  return <div className="capstone-chat-artifacts" aria-label="当前运行结果引用">
    <span className="capstone-chat-artifacts-label"><FileCheck2 aria-hidden="true" /> 当前运行</span>
    {modelSummary && <span title={modelSummary.modelRevision}>{modelSummary.modelId} · {modelSummary.implementationFamily}</span>}
    {resultRefs.length > 0 && <span>结果 {resultRefs.length}</span>}
    {evidenceRefs.length > 0 && <span>证据 {evidenceRefs.length}</span>}
    {admitted && <span className="is-admitted">已准入</span>}
  </div>
}

function ChatMessage({ onRegenerate, onEditInstruction, modelSummary }: { onRegenerate?: (attemptId: string) => Promise<void>; onEditInstruction?: (text: string) => void; modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string } }) {
  const activityRef = useRef<HTMLDetailsElement>(null)
  const role = useAuiState((state) => state.message.role)
  const content = useAuiState((state) => state.message.content)
  const id = useAuiState((state) => state.message.id)
  const status = useAuiState((state) => state.message.status)
  const custom = useAuiState((state) => state.message.metadata?.custom) as Record<string, unknown> | undefined
  const hasText = messageText({ content }).trim().length > 0
  const text = messageText({ content })
  const attemptId = id.replace(/^assistant-/, '')
  const evidenceRefs = stringRefs(custom?.evidenceRefs)
  const resultRefs = stringRefs(custom?.resultRefs)
  const admission = custom?.admission
  const startedAt = typeof custom?.startedAt === 'string' ? custom.startedAt : undefined
  const durationMs = typeof custom?.durationMs === 'number' ? custom.durationMs : undefined
  const toolCount = typeof custom?.toolCount === 'number' ? custom.toolCount : 0
  const activities = Array.isArray(custom?.activities) ? custom.activities as ChatActivity[] : []
  const [activityOpen, setActivityOpen] = useState(status?.type === 'running')
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
  return <MessagePrimitive.Root className={`capstone-chat-message is-${role}`}>
    <div className="capstone-chat-body">
      <span className="capstone-chat-role">{role === 'user' ? '你' : 'CAPSTONE'}</span>
      {hasText
        ? <MessagePrimitive.Parts components={{ Text: role === 'assistant' ? () => <MessagePartPrimitive.Text smooth={false} render={<MarkdownMessage />} /> : () => <MessagePartPrimitive.Text smooth={false} component="p" /> }} />
        : role === 'assistant' && <span className={`capstone-chat-placeholder${terminalWithoutText ? ' is-terminal' : ''}`}>{terminalWithoutText ? 'Attempt 已结束，暂无可显示的回答。' : '正在生成回答…'}</span>}
    </div>
    {role === 'user' && typeof custom?.receipt === 'string' && <div className="capstone-chat-receipt"><Check aria-hidden="true" /> {custom.receipt}</div>}
    {role === 'assistant' && <RunDuration startedAt={startedAt} durationMs={durationMs} running={status?.type === 'running'} />}
    {role === 'assistant' && <RunArtifacts resultRefs={resultRefs} evidenceRefs={evidenceRefs} admission={admission} modelSummary={modelSummary} />}
    {(hasText || terminalWithoutText) && <ChatActions role={role} text={text} evidenceRefs={evidenceRefs} toolCount={activities.length || toolCount} activityOpen={activityOpen} onShowActivity={toggleActivity} onEditInstruction={role === 'user' ? onEditInstruction : undefined} onRegenerate={role === 'assistant' && onRegenerate ? () => onRegenerate(attemptId) : undefined} />}
    {role === 'assistant' && <AttemptActivity activities={activities} running={status?.type === 'running'} open={status?.type === 'running' || activityOpen} startedAt={startedAt} durationMs={durationMs} detailsRef={activityRef} />}
  </MessagePrimitive.Root>
}

function ComposerSurface({ mode, disabled, isRunning, editRequest }: { mode: SendMode; disabled: boolean; isRunning: boolean; editRequest?: { text: string; nonce: number } }) {
  const aui = useAui()
  const isEmpty = useAuiState((state) => state.composer.isEmpty)
  useEffect(() => {
    if (editRequest) aui.composer.setText(editRequest.text)
  }, [aui, editRequest])
  return <ComposerPrimitive.Root className="capstone-composer-root" data-running={isRunning ? 'true' : 'false'} data-empty={isEmpty ? 'true' : 'false'}>
    <ComposerPrimitive.Input aria-label="Thread 指令" placeholder={disabled ? '当前状态暂不可提交新指令' : '围绕当前电网模型输入指令…'} disabled={disabled} submitMode="ctrlEnter" />
    <div className="capstone-composer-footer"><span>Enter 换行 · ⌘/Ctrl + Enter 发送</span><div className="capstone-composer-actions">
      {isRunning ? <ComposerPrimitive.Cancel className="capstone-chat-stop" aria-label="停止生成" title="停止生成"><Square aria-hidden="true" /></ComposerPrimitive.Cancel> : !disabled && !isEmpty ? <ComposerPrimitive.Send className="capstone-chat-send" aria-label="发送指令" title={mode === 'professional' ? '发送专业请求' : '发送指令'}><SendHorizontal aria-hidden="true" /></ComposerPrimitive.Send> : null}
    </div></div>
  </ComposerPrimitive.Root>
}

export type CapstoneAssistantThreadProps = {
  events: readonly EventEnvelope[]
  disabled: boolean
  isRunning: boolean
  activity: readonly (ChatActivity | string)[]
  onSend: (mode: SendMode, text: string) => Promise<void>
  onCancel: () => Promise<void>
  onRegenerate?: (attemptId: string) => Promise<void>
  modelSummary?: { modelId: string; implementationFamily: string; modelRevision: string; contextId: string }
}

/** Assistant-ui is the presentation runtime; Capstone projection remains authoritative. */
export default function CapstoneAssistantThread({ events, disabled, isRunning, activity, onSend, onCancel, onRegenerate, modelSummary }: CapstoneAssistantThreadProps) {
  const messages = useMemo(() => projectAssistantMessages(events), [events])
  const [mode, setMode] = useState<SendMode>('automatic')
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
      if (text.trim()) await onSend(mode, text.trim())
    },
    onEdit: async (message) => {
      const text = messageText(message)
      if (text.trim()) await onSend(mode, text.trim())
    },
    onCancel,
  })

  return <AssistantRuntimeProvider runtime={runtime}>
    <div className="capstone-assistant-thread" data-testid="assistant-ui-chat">
      <div className="capstone-assistant-runtime-label"><span className="assistant-live-dot" />CAPSTONE <span>· HARNESS</span><small>实时响应</small></div>
      <ThreadPrimitive.Root className="capstone-chat-runtime">
        {typeof ResizeObserver === 'undefined' ? <div className="capstone-chat-viewport">
          {messages.length === 0 && <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><span>可以先问模型状态，也可以直接发起潮流、约束或线路筛查分析。</span></div>}
          <ThreadPrimitive.Messages components={{ Message: () => <ChatMessage onRegenerate={onRegenerate} onEditInstruction={(text) => setEditRequest({ text, nonce: Date.now() })} modelSummary={modelSummary} /> }} />
        </div> : <ThreadPrimitive.Viewport className="capstone-chat-viewport" scrollToBottomOnInitialize={false}>
          {messages.length === 0 && <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><span>可以先问模型状态，也可以直接发起潮流、约束或线路筛查分析。</span></div>}
          <ThreadPrimitive.Messages components={{ Message: () => <ChatMessage onRegenerate={onRegenerate} onEditInstruction={(text) => setEditRequest({ text, nonce: Date.now() })} modelSummary={modelSummary} /> }} />
        </ThreadPrimitive.Viewport>}
        {legacyActivity && normalizedActivity.length > 0 && <details className="capstone-chat-activity" open={isRunning}>
          <summary><Activity aria-hidden="true" /><span>{isRunning ? '正在执行' : '已完成'} {normalizedActivity.length} 个步骤</span><small>查看运行过程</small></summary>
          <div className="capstone-chat-activity-list">{normalizedActivity.slice(-5).map((item) => <div key={item.id} className={`capstone-chat-activity-item is-${item.status}`}><span className="capstone-chat-activity-icon" aria-hidden="true" /> <span><strong>{item.label}</strong><small>{item.source}</small></span></div>)}</div>
        </details>}
        <div className="capstone-chat-composer">
          <div className="capstone-chat-mode" role="group" aria-label="指令模式">
            <button type="button" className={mode === 'automatic' ? 'is-selected' : ''} onClick={() => setMode('automatic')} disabled={disabled}>自动识别</button>
            <button type="button" className={mode === 'professional' ? 'is-selected' : ''} onClick={() => setMode('professional')} disabled={disabled}>专业分析</button>
          </div>
          <ComposerSurface mode={mode} disabled={disabled} isRunning={isRunning} editRequest={editRequest} />
        </div>
      </ThreadPrimitive.Root>
    </div>
  </AssistantRuntimeProvider>
}
