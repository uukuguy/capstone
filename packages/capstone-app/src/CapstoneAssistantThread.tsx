import { useMemo, useState, type ReactNode } from 'react'
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type ThreadMessageLike,
  useAuiState,
  useExternalStoreRuntime,
} from '@assistant-ui/react'
import { Activity, Check, Copy, MoreHorizontal, RotateCcw, SendHorizontal, Square, ThumbsDown, ThumbsUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { EventEnvelope } from './threadProtocol'

type SendMode = 'automatic' | 'ordinary' | 'professional'

export type ChatActivity = {
  id: string
  label: string
  source: string
  status: 'running' | 'completed' | 'failed'
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

function activitySource(event: EventEnvelope): string {
  const binding = typeof event.payload.binding_id === 'string' ? event.payload.binding_id : 'capstone'
  const capability = typeof event.payload.capability === 'string' ? event.payload.capability : toolName(event)
  return `${binding} · ${capability}`
}

export function projectAssistantActivity(events: readonly EventEnvelope[]): ChatActivity[] {
  const grouped = new Map<string, ChatActivity>()
  for (const event of events) {
    if (!['tool_started', 'tool_completed', 'tool_failed', 'tool_cancelled'].includes(event.eventType)) continue
    const id = toolName(event)
    const status = event.eventType === 'tool_started'
      ? 'running'
      : event.eventType === 'tool_failed' ? 'failed' : 'completed'
    grouped.set(id, {
      id,
      label: TOOL_LABELS[id] || id.replaceAll('_', ' '),
      source: activitySource(event),
      status,
    })
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

export function projectAssistantMessages(events: readonly EventEnvelope[]): ThreadMessageLike[] {
  const messages: ThreadMessageLike[] = []
  const assistantByAttempt = new Map<string, ThreadMessageLike & { content: string }>()
  for (const event of events) {
    if (event.eventType === 'command_accepted' && (event.payload.kind === 'send_auto' || event.payload.kind === 'send_ordinary' || event.payload.kind === 'send_professional')) {
      const text = payloadText(event, true)
      if (text) messages.push({ id: `user-${event.eventId}`, role: 'user', content: text, metadata: { custom: { mode: commandMode(event), eventId: event.eventId } } })
      continue
    }
    if (event.eventType === 'assistant_text_delta') {
      const key = event.attemptId || event.turnId || `event-${event.eventId}`
      const existing = assistantByAttempt.get(key)
      if (existing) existing.content += payloadText(event)
      else {
        const message = { id: `assistant-${key}`, role: 'assistant' as const, content: payloadText(event), status: { type: 'running' as const }, metadata: { custom: { attemptId: key, source: 'capstone-harness' } } }
        assistantByAttempt.set(key, message)
        messages.push(message)
      }
      continue
    }
    if (event.eventType === 'attempt_completed' || event.eventType === 'attempt_failed' || event.eventType === 'attempt_cancelled' || event.eventType === 'attempt_interrupted') {
      const key = event.attemptId || event.turnId
      let message = key ? assistantByAttempt.get(key) : undefined
      const answer = event.eventType === 'attempt_completed' && typeof event.payload.answer === 'string'
        ? event.payload.answer
        : ''
      if (!message && key && answer) {
        message = {
          id: `assistant-${key}`,
          role: 'assistant' as const,
          content: answer,
          status: { type: 'running' as const },
          metadata: { custom: { attemptId: key, source: 'capstone-harness' } },
        }
        assistantByAttempt.set(key, message)
        messages.push(message)
      } else if (message && !message.content && answer) {
        message.content = answer
      }
      if (message) {
        const status = event.eventType === 'attempt_completed'
          ? { type: 'complete' as const, reason: 'stop' as const }
          : { type: 'incomplete' as const, reason: event.eventType === 'attempt_cancelled' ? 'cancelled' as const : event.eventType === 'attempt_failed' ? 'error' as const : 'other' as const }
        ;(message as unknown as { status?: ThreadMessageLike['status'] }).status = status
      }
    }
  }
  return messages.map((message) => message.role === 'assistant' && typeof message.content === 'string'
    ? { ...message, content: [{ type: 'text' as const, text: message.content }] }
    : message)
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
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{typeof children === 'string' ? children : String(children ?? '')}</ReactMarkdown>
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

function IconAction({ label, onClick, children }: { label: string; onClick?: () => void; children: ReactNode }) {
  return <button type="button" className="capstone-chat-action" aria-label={label} title={label} onClick={onClick}>{children}</button>
}

function ChatActions({ role, text, onRegenerate }: { role: string; text: string; onRegenerate?: () => Promise<void> }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    if (await copyToClipboard(text)) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    }
  }
  if (role === 'user') {
    return <div className="capstone-chat-actions" aria-label="消息操作"><IconAction label={copied ? '已复制' : '复制指令'} onClick={() => void copy()}>{copied ? <Check /> : <Copy />}</IconAction></div>
  }
  return <div className="capstone-chat-actions" aria-label="回答操作">
    <IconAction label={copied ? '已复制' : '复制回答'} onClick={() => void copy()}>{copied ? <Check /> : <Copy />}</IconAction>
    {onRegenerate && <IconAction label="重新运行回答" onClick={() => void onRegenerate()}><RotateCcw /></IconAction>}
    <IconAction label="回答有帮助"><ThumbsUp /></IconAction>
    <IconAction label="回答需改进"><ThumbsDown /></IconAction>
    <IconAction label="更多回答操作"><MoreHorizontal /></IconAction>
  </div>
}

function ChatMessage({ onRegenerate }: { onRegenerate?: (attemptId: string) => Promise<void> }) {
  const role = useAuiState((state) => state.message.role)
  const content = useAuiState((state) => state.message.content)
  const id = useAuiState((state) => state.message.id)
  const hasText = messageText({ content }).trim().length > 0
  const text = messageText({ content })
  const attemptId = id.replace(/^assistant-/, '')
  return <MessagePrimitive.Root className={`capstone-chat-message is-${role}`}>
    <div className="capstone-chat-body">
      <span className="capstone-chat-role">{role === 'user' ? '你' : 'CAPSTONE'}</span>
      {hasText
        ? <MessagePrimitive.Parts components={{ Text: role === 'assistant' ? () => <MessagePartPrimitive.Text smooth={false} render={<MarkdownMessage />} /> : () => <MessagePartPrimitive.Text smooth={false} component="p" /> }} />
        : role === 'assistant' && <span className="capstone-chat-placeholder">正在生成回答…</span>}
      {hasText && <ChatActions role={role} text={text} onRegenerate={role === 'assistant' && onRegenerate ? () => onRegenerate(attemptId) : undefined} />}
    </div>
  </MessagePrimitive.Root>
}

function ComposerSurface({ mode, disabled, isRunning }: { mode: SendMode; disabled: boolean; isRunning: boolean }) {
  const isEmpty = useAuiState((state) => state.composer.isEmpty)
  return <ComposerPrimitive.Root className="capstone-composer-root" data-running={isRunning ? 'true' : 'false'} data-empty={isEmpty ? 'true' : 'false'}>
    <ComposerPrimitive.Input aria-label="Thread 指令" placeholder={disabled ? '当前状态暂不可提交新指令' : '围绕当前电网模型输入指令…'} disabled={disabled} submitMode="ctrlEnter" />
    <div className="capstone-composer-footer"><span>Enter 换行 · ⌘/Ctrl + Enter 发送</span><div className="capstone-composer-actions">
      {isRunning ? <ComposerPrimitive.Cancel className="capstone-chat-stop" aria-label="停止生成" title="停止生成"><Square aria-hidden="true" /></ComposerPrimitive.Cancel> : !disabled ? <ComposerPrimitive.Send className="capstone-chat-send" aria-label="发送指令" title={mode === 'professional' ? '发送专业请求' : '发送指令'}><SendHorizontal aria-hidden="true" /></ComposerPrimitive.Send> : null}
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
}

/** Assistant-ui is the presentation runtime; Capstone projection remains authoritative. */
export default function CapstoneAssistantThread({ events, disabled, isRunning, activity, onSend, onCancel, onRegenerate }: CapstoneAssistantThreadProps) {
  const messages = useMemo(() => projectAssistantMessages(events), [events])
  const [mode, setMode] = useState<SendMode>('automatic')
  const normalizedActivity = activity.map((item) => typeof item === 'string' ? { id: item, label: item, source: 'capstone-harness', status: 'completed' as const } : item)
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    convertMessage: (message) => message,
    isSendDisabled: disabled,
    isRunning,
    onNew: async (message) => {
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
          <ThreadPrimitive.Messages components={{ Message: () => <ChatMessage onRegenerate={onRegenerate} /> }} />
        </div> : <ThreadPrimitive.Viewport className="capstone-chat-viewport" scrollToBottomOnInitialize={false}>
          {messages.length === 0 && <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><span>可以先问模型状态，也可以直接发起潮流、约束或线路筛查分析。</span></div>}
          <ThreadPrimitive.Messages components={{ Message: () => <ChatMessage onRegenerate={onRegenerate} /> }} />
        </ThreadPrimitive.Viewport>}
        {normalizedActivity.length > 0 && <details className="capstone-chat-activity" open={isRunning}>
          <summary><Activity aria-hidden="true" /><span>{isRunning ? '正在执行' : '已完成'} {normalizedActivity.length} 个步骤</span><small>查看运行过程</small></summary>
          <div className="capstone-chat-activity-list">{normalizedActivity.slice(-5).map((item) => <div key={item.id} className={`capstone-chat-activity-item is-${item.status}`}><span className="capstone-chat-activity-icon" aria-hidden="true" /> <span><strong>{item.label}</strong><small>{item.source}</small></span></div>)}</div>
        </details>}
        <div className="capstone-chat-composer">
          <div className="capstone-chat-mode" role="group" aria-label="指令模式">
            <button type="button" className={mode === 'automatic' ? 'is-selected' : ''} onClick={() => setMode('automatic')} disabled={disabled}>自动识别</button>
            <button type="button" className={mode === 'professional' ? 'is-selected' : ''} onClick={() => setMode('professional')} disabled={disabled}>专业分析</button>
          </div>
          <ComposerSurface mode={mode} disabled={disabled} isRunning={isRunning} />
        </div>
      </ThreadPrimitive.Root>
    </div>
  </AssistantRuntimeProvider>
}
