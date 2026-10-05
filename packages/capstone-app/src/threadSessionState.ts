import { buildThreadCommand, type ThreadCommand } from './threadClient'

const MAX_STORED_BYTES = 64 * 1024
const MAX_DRAFT_CHARACTERS = 16_000

export function readDraft(key?: string): string {
  if (!key) return ''
  try {
    const draft = sessionStorage.getItem(`${key}.draft`)
    if (draft) return draft.slice(0, MAX_DRAFT_CHARACTERS)
    const text = sessionStorage.getItem(`${key}.commands`)
    if (!text || new TextEncoder().encode(text).byteLength > MAX_STORED_BYTES) return ''
    const commands = JSON.parse(text)
    const command = Array.isArray(commands) && commands.length === 1 ? commands[0] : null
    return command && ['send_auto', 'send_ordinary', 'send_professional'].includes(command.kind)
      && typeof command.payload?.text === 'string' ? command.payload.text.slice(0, MAX_DRAFT_CHARACTERS) : ''
  } catch { return '' }
}

export function writeDraft(key: string | undefined, text: string): void {
  if (!key) return
  try {
    if (text) sessionStorage.setItem(`${key}.draft`, text.slice(0, MAX_DRAFT_CHARACTERS))
    else sessionStorage.removeItem(`${key}.draft`)
  } catch { /* Keep the live Composer when browser storage is unavailable. */ }
}

export function storageNamespace(origin: string): string {
  const namespaceKey = 'capstone.thread.storageSession'
  let session = ''
  try { session = sessionStorage.getItem(namespaceKey) || '' } catch { /* memory fallback */ }
  if (!session) {
    session = crypto.randomUUID()
    try { sessionStorage.setItem(namespaceKey, session) } catch { /* memory fallback */ }
  }
  return `capstone.thread.${encodeURIComponent(origin || window.location.origin)}.${session}`
}

export function rotateStorageNamespace(): void {
  try { sessionStorage.setItem('capstone.thread.storageSession', crypto.randomUUID()) } catch { /* memory fallback */ }
}

export function readPendingCommands(key: string | undefined, threadId: string): ThreadCommand[] {
  if (!key) return []
  try {
    const text = sessionStorage.getItem(`${key}.commands`)
    if (!text || new TextEncoder().encode(text).byteLength > MAX_STORED_BYTES) return []
    const documents: unknown = JSON.parse(text)
    if (!Array.isArray(documents) || documents.length > 1) return []
    return documents.map((item) => {
      if (!item || typeof item !== 'object' || item.schema !== 'capstone-command/1'
          || item.thread_id !== threadId || typeof item.expected_event_seq !== 'number'
          || !Number.isSafeInteger(item.expected_event_seq) || item.expected_event_seq < 0
          || !item.payload || typeof item.payload !== 'object' || Array.isArray(item.payload)) throw new Error('Invalid stored command')
      return buildThreadCommand({ threadId, runId: item.run_id, kind: item.kind,
        commandId: item.command_id, idempotencyKey: item.idempotency_key,
        expectedEventSeq: item.expected_event_seq, payload: item.payload })
    })
  } catch { return [] }
}

export function writePendingCommands(key: string | undefined, commands: readonly ThreadCommand[]): void {
  if (!key) return
  try {
    if (!commands.length) sessionStorage.removeItem(`${key}.commands`)
    else {
      const text = JSON.stringify(commands)
      if (commands.length === 1 && new TextEncoder().encode(text).byteLength <= MAX_STORED_BYTES) sessionStorage.setItem(`${key}.commands`, text)
    }
  } catch { /* Exact in-memory command recovery remains available. */ }
}

export function reconnectDelay(failures: number): number {
  return Math.min(1000 * 2 ** Math.min(failures, 4), 15_000)
}

export function canReconnect(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') return false
  const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined
  return status === undefined || status === 409 || status === 429 || (typeof status === 'number' && status >= 500)
}
