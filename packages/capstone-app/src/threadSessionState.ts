import {applicationCapacity,assertCapacity,exceedsCapacity,CapacityError,rethrowDebugCapacity} from './applicationCapacity'
import { buildThreadCommand, type ThreadCommand } from './threadClient'
import type { AnyThreadCommand } from './threadClient'
import { parseStoredWorkCommand } from './threadWorkProtocol'
import { isThreadVersionError } from './threadHttpTransport'
import {currentWorkspaceName} from './workspaceName'


export type FollowupTarget = { threadId: string; attemptId: string; modelId: string; label: string }

export function readFollowup(key: string | undefined, threadId: string): FollowupTarget | undefined {
  if (!key) return undefined
  try {
    const text = sessionStorage.getItem(`${key}.followup`)
    if (!text || exceedsCapacity(new TextEncoder().encode(text).byteLength,'ui_followup_bytes')) return undefined
    const value = JSON.parse(text)
    if (value?.threadId !== threadId || typeof value.attemptId !== 'string' || !/^[a-z][a-z0-9_-]{0,63}$/.test(value.attemptId) ||
        typeof value.modelId !== 'string' || value.modelId.length > 256 ||
        typeof value.label !== 'string' || exceedsCapacity(value.label.length,'ui_session_title_chars')) return undefined
    return { threadId, attemptId: value.attemptId, modelId: value.modelId, label: value.label }
  } catch (error) { rethrowDebugCapacity(error); return undefined }
}

export function writeFollowup(key: string | undefined, target?: FollowupTarget): void {
  if (!key) return
  try {
    if (target) sessionStorage.setItem(`${key}.followup`, JSON.stringify(target))
    else sessionStorage.removeItem(`${key}.followup`)
  } catch { /* The live selection remains available without browser storage. */ }
}

function checkedDraft(text:string):string{assertCapacity(text.length,'input_text_chars');return text}

export function readDraft(key?: string): string {
  if (!key) return ''
  try {
    const draft = sessionStorage.getItem(`${key}.draft`)
    if (draft) {assertCapacity(draft.length,'input_text_chars');return draft}
    const text = sessionStorage.getItem(`${key}.commands`)
    if (!text) return ''
    assertCapacity(new TextEncoder().encode(text).byteLength,'command_bytes')
    const commands = JSON.parse(text)
    const command = Array.isArray(commands) && commands.length === 1 ? commands[0] : null
    return command && ['send_auto', 'send_ordinary', 'send_professional'].includes(command.kind)
      && typeof command.payload?.text === 'string' ? checkedDraft(command.payload.text) : ''
  } catch (error) { if(error instanceof CapacityError)throw error; return '' }
}

export function writeDraft(key: string | undefined, text: string): void {
  if (!key) return
  assertCapacity(text.length,'input_text_chars')
  try {
    if (text) sessionStorage.setItem(`${key}.draft`, text)
    else sessionStorage.removeItem(`${key}.draft`)
  } catch { /* Keep the live Composer when browser storage is unavailable. */ }
}

export function storageNamespace(origin: string,workspace=currentWorkspaceName()): string {
  const namespaceKey = 'capstone.thread.storageSession'
  let session = ''
  try { session = sessionStorage.getItem(namespaceKey) || '' } catch { /* memory fallback */ }
  if (!session) {
    session = crypto.randomUUID()
    try { sessionStorage.setItem(namespaceKey, session) } catch { /* memory fallback */ }
  }
  return `capstone.thread.${encodeURIComponent(origin || window.location.origin)}.${session}${workspace==='enterprise'?'':`.workspace.${encodeURIComponent(workspace)}`}`
}

export function rotateStorageNamespace(): void {
  try { sessionStorage.setItem('capstone.thread.storageSession', crypto.randomUUID()) } catch { /* memory fallback */ }
  window.dispatchEvent(new Event('capstone-thread-access-changed'))
}

export function readPendingCommands(key: string | undefined, threadId: string): AnyThreadCommand[] {
  if (!key) return []
  try {
    const text = sessionStorage.getItem(`${key}.commands`)
    if (!text) return []
    assertCapacity(new TextEncoder().encode(text).byteLength,'command_bytes')
    const documents: unknown = JSON.parse(text)
    if (!Array.isArray(documents) || documents.length > 1) return []
    return documents.map((item) => {
      if (item?.schema === 'capstone-command/2') return parseStoredWorkCommand(item, threadId)
      if (!item || typeof item !== 'object' || item.schema !== 'capstone-command/1'
          || item.thread_id !== threadId || typeof item.expected_event_seq !== 'number'
          || !Number.isSafeInteger(item.expected_event_seq) || item.expected_event_seq < 0
          || !item.payload || typeof item.payload !== 'object' || Array.isArray(item.payload)) throw new Error('Invalid stored command')
      return buildThreadCommand({ threadId, runId: item.run_id, kind: item.kind,
        commandId: item.command_id, idempotencyKey: item.idempotency_key,
        expectedEventSeq: item.expected_event_seq, payload: item.payload })
    })
  } catch (error) { if(error instanceof CapacityError)throw error; return [] }
}

export function writePendingCommands(key: string | undefined, commands: readonly AnyThreadCommand[]): void {
  if (!key) return
  try {
    if (!commands.length) sessionStorage.removeItem(`${key}.commands`)
    else {
      const text = JSON.stringify(commands)
      assertCapacity(new TextEncoder().encode(text).byteLength,'command_bytes')
      if(commands.length!==1)throw new Error('只能恢复一个待确认请求')
      sessionStorage.setItem(`${key}.commands`, text)
    }
  } catch (error) { if(error instanceof CapacityError)throw error; /* Exact in-memory command recovery remains available. */ }
}

export function reconnectDelay(failures: number): number {
  return Math.min(applicationCapacity('ui_reconnect_base_ms') * 2 ** Math.min(failures, 30), applicationCapacity('ui_reconnect_max_ms'))
}

export function canReconnect(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') return false
  if (error instanceof CapacityError || isThreadVersionError(error)) return false
  const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined
  return status === undefined || status === 409 || status === 429 || (typeof status === 'number' && status >= 500)
}
