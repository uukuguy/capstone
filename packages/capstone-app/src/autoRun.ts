import type { CreatedSession, SessionStatus } from './types'

export type AutomaticAction = 'start' | 'wait' | 'close' | 'done' | { submit: number }

export function nextAutomaticAction(status: SessionStatus | null, count: number): AutomaticAction {
  if (!status) return 'start'
  if (status.state === 'completed' || status.state === 'failed' || status.state === 'interrupted') {
    return 'done'
  }
  if (status.state !== 'ready' || status.accepted_turns > status.completed_turns) {
    return 'wait'
  }
  return status.completed_turns < count ? { submit: status.completed_turns + 1 } : 'close'
}

type AutomaticClient = {
  createSession: (applicationId: string, caseId: string) => Promise<CreatedSession>
  status: (sessionId: string) => Promise<SessionStatus>
  submitTurn: (sessionId: string, instruction: string, key: string) => Promise<unknown>
  close: (sessionId: string, key: string) => Promise<unknown>
}

function waitForNextPoll(signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve()
    const timer = setTimeout(finish, 400)
    function finish() {
      clearTimeout(timer)
      signal.removeEventListener('abort', finish)
      resolve()
    }
    signal.addEventListener('abort', finish, { once: true })
  })
}

export async function runAutomaticSession(
  client: AutomaticClient, applicationId: string, caseId: string,
  instructions: readonly string[], initialSessionId: string | null,
  signal: AbortSignal, keys: Map<string, string>,
  onCreated: (created: CreatedSession) => void,
  onStatus: (status: SessionStatus) => void,
  wait: (signal: AbortSignal) => Promise<void> = waitForNextPoll,
): Promise<string> {
  let sessionId = initialSessionId
  if (!sessionId) {
    const created = await client.createSession(applicationId, caseId)
    sessionId = created.session_id
    onCreated(created)
  }
  while (!signal.aborted) {
    const status = await client.status(sessionId)
    if (signal.aborted) return sessionId
    onStatus(status)
    const action = nextAutomaticAction(status, instructions.length)
    if (action === 'done') return sessionId
    if (action === 'wait') {
      await wait(signal)
      continue
    }
    if (action === 'start') throw new Error('运行会话未建立')
    const commandId = action === 'close' ? 'close' : `turn:${action.submit}`
    const keyId = `${sessionId}:${commandId}`
    let key = keys.get(keyId)
    if (!key) {
      key = crypto.randomUUID()
      keys.set(keyId, key)
    }
    if (action === 'close') {
      await client.close(sessionId, key)
      onStatus({ ...status, state: 'closing' })
    } else {
      await client.submitTurn(sessionId, instructions[action.submit - 1], key)
      onStatus({ ...status, state: 'executing', accepted_turns: action.submit })
    }
    await wait(signal)
  }
  return sessionId
}
