import { commandKey } from './commandKey'

type StoredRun = { createKey: string; sessionId: string | null }
type StoredSelection = { applicationId: string; caseId: string }

const runPrefix = 'capstone-demo-run/v1/'
const selectionKey = 'capstone-demo-selection/v1'

function storage(): Storage | null {
  try { return window.sessionStorage } catch { return null }
}

function runKey(applicationId: string, caseId: string): string {
  return `${runPrefix}${encodeURIComponent(applicationId)}/${encodeURIComponent(caseId)}`
}

export function readRun(applicationId: string, caseId: string): StoredRun | null {
  const value = storage()?.getItem(runKey(applicationId, caseId))
  if (!value) return null
  try {
    const parsed: unknown = JSON.parse(value)
    if (parsed && typeof parsed === 'object' && 'createKey' in parsed &&
        typeof parsed.createKey === 'string' && /^[0-9a-f]{32}$/.test(parsed.createKey) &&
        'sessionId' in parsed && (parsed.sessionId === null ||
          typeof parsed.sessionId === 'string' && /^session-[0-9a-f]{24}$/.test(parsed.sessionId))) {
      return parsed as StoredRun
    }
  } catch { /* A malformed tab record cannot affect the API session. */ }
  return null
}

export function ensureCreateKey(applicationId: string, caseId: string): string {
  const previous = readRun(applicationId, caseId)
  if (previous) return previous.createKey
  const createKey = commandKey()
  storage()?.setItem(runKey(applicationId, caseId), JSON.stringify({ createKey, sessionId: null }))
  return createKey
}

export function rememberSession(applicationId: string, caseId: string,
                                createKey: string, sessionId: string): void {
  storage()?.setItem(runKey(applicationId, caseId), JSON.stringify({ createKey, sessionId }))
}

export function forgetRun(applicationId: string, caseId: string): void {
  storage()?.removeItem(runKey(applicationId, caseId))
}

export function readSelection(): StoredSelection | null {
  const value = storage()?.getItem(selectionKey)
  if (!value) return null
  try {
    const parsed: unknown = JSON.parse(value)
    if (parsed && typeof parsed === 'object' && 'applicationId' in parsed &&
        'caseId' in parsed && typeof parsed.applicationId === 'string' &&
        typeof parsed.caseId === 'string') return parsed as StoredSelection
  } catch { /* Ignore malformed tab state. */ }
  return null
}

export function rememberSelection(selection: StoredSelection): void {
  storage()?.setItem(selectionKey, JSON.stringify(selection))
}
