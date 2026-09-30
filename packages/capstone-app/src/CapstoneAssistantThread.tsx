import { useMemo, useState } from 'react'
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
import type { EventEnvelope } from './threadProtocol'

type SendMode = 'ordinary' | 'professional'

function payloadText(event: EventEnvelope, nested = false): string {
  const source = nested && event.payload.payload && typeof event.payload.payload === 'object' && !Array.isArray(event.payload.payload)
    ? event.payload.payload as Record<string, unknown>
    : event.payload
  const value = source.text
  return typeof value === 'string' ? value : ''
}

function commandMode(event: EventEnvelope): SendMode {
  return event.payload.kind === 'send_professional' ? 'professional' : 'ordinary'
}

export function projectAssistantMessages(events: readonly EventEnvelope[]): ThreadMessageLike[] {
  const messages: ThreadMessageLike[] = []
  const assistantByAttempt = new Map<string, ThreadMessageLike & { content: string }>()
  for (const event of events) {
    if (event.eventType === 'command_accepted' && (event.payload.kind === 'send_ordinary' || event.payload.kind === 'send_professional')) {
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
      const message = key ? assistantByAttempt.get(key) : undefined
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

function ChatMessage() {
  const role = useAuiState((state) => state.message.role)
  return <MessagePrimitive.Root className={`capstone-chat-message is-${role}`}>
    <div className="capstone-chat-avatar" aria-hidden="true">{role === 'user' ? '你' : 'C'}</div>
    <div className="capstone-chat-body"><span className="capstone-chat-role">{role === 'user' ? '你' : 'CAPSTONE · HARNESS'}</span><MessagePrimitive.Parts components={{ Text: () => <MessagePartPrimitive.Text smooth={false} /> }} /></div>
  </MessagePrimitive.Root>
}

export type CapstoneAssistantThreadProps = {
  events: readonly EventEnvelope[]
  disabled: boolean
  isRunning: boolean
  activity: readonly string[]
  onSend: (mode: SendMode, text: string) => Promise<void>
  onCancel: () => Promise<void>
}

/** Assistant-ui is the presentation runtime; Capstone projection remains authoritative. */
export default function CapstoneAssistantThread({ events, disabled, isRunning, activity, onSend, onCancel }: CapstoneAssistantThreadProps) {
  const messages = useMemo(() => projectAssistantMessages(events), [events])
  const [mode, setMode] = useState<SendMode>('ordinary')
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
      <div className="capstone-assistant-runtime-label"><span className="assistant-live-dot" />assistant-ui <span>· Capstone projection</span></div>
      <ThreadPrimitive.Root className="capstone-chat-runtime">
        {typeof ResizeObserver === 'undefined' ? <div className="capstone-chat-viewport">
          {messages.length === 0 && <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><span>可以先问模型状态，也可以直接发起潮流、约束或线路筛查分析。</span></div>}
          <ThreadPrimitive.Messages components={{ Message: ChatMessage }} />
        </div> : <ThreadPrimitive.Viewport className="capstone-chat-viewport" scrollToBottomOnInitialize={false}>
          {messages.length === 0 && <div className="capstone-chat-empty"><strong>围绕当前电网模型开始对话</strong><span>可以先问模型状态，也可以直接发起潮流、约束或线路筛查分析。</span></div>}
          <ThreadPrimitive.Messages components={{ Message: ChatMessage }} />
        </ThreadPrimitive.Viewport>}
        {activity.length > 0 && <div className="capstone-chat-activity" aria-label="工具活动">
          {activity.slice(-3).map((item, index) => <span key={`${item}-${index}`}><i />{item}</span>)}
        </div>}
        <div className="capstone-chat-composer">
          <div className="capstone-chat-mode" role="group" aria-label="指令模式">
            <button type="button" className={mode === 'ordinary' ? 'is-selected' : ''} onClick={() => setMode('ordinary')} disabled={disabled}>普通对话</button>
            <button type="button" className={mode === 'professional' ? 'is-selected' : ''} onClick={() => setMode('professional')} disabled={disabled}>专业分析</button>
          </div>
          <ComposerPrimitive.Root className="capstone-composer-root">
            <ComposerPrimitive.Input aria-label="Thread 指令" placeholder={disabled ? '当前状态暂不可提交新指令' : '围绕当前电网模型输入指令…'} disabled={disabled} submitMode="ctrlEnter" />
            <div className="capstone-composer-footer"><span>Enter 换行 · ⌘/Ctrl + Enter 发送</span>
              {isRunning ? <ComposerPrimitive.Cancel className="capstone-chat-stop">停止</ComposerPrimitive.Cancel> : !disabled ? <ComposerPrimitive.Send className="capstone-chat-send">{mode === 'ordinary' ? '发送普通指令' : '发送专业请求'}</ComposerPrimitive.Send> : null}
            </div>
          </ComposerPrimitive.Root>
        </div>
      </ThreadPrimitive.Root>
    </div>
  </AssistantRuntimeProvider>
}
