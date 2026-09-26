import type {
  Catalog, CommittedTurn, CreatedSession, SessionEvent, SessionStatus,
} from './types'

const MAX_RESPONSE_BYTES = 2_100_000
const MAX_EVENT_BYTES = 1_100_000

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function boundedText(response: Response): Promise<string> {
  if (!response.body) return ''
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let result = ''
  let bytes = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    bytes += value.byteLength
    if (bytes > MAX_RESPONSE_BYTES) {
      await reader.cancel()
      throw new Error('响应超过允许大小')
    }
    result += decoder.decode(value, { stream: true })
  }
  return result + decoder.decode()
}

export class CapstoneClient {
  private readonly base: string

  constructor(baseUrl: string, private readonly token: string,
              private readonly fetcher: typeof fetch = fetch) {
    const trimmed = baseUrl.trim().replace(/\/$/, '')
    if (trimmed && !/^https?:\/\/[^/]+$/.test(trimmed)) {
      throw new Error('API 地址无效')
    }
    this.base = trimmed
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const response = await this.fetcher.call(globalThis, this.base + path, {
      ...init,
      credentials: 'omit',
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${this.token}`,
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })
    if (!response.ok) {
      if (response.status === 401) throw new ApiError(401, '访问凭证无效，请重新输入。')
      if (response.status === 409) throw new ApiError(409, '当前运行状态暂不接受该操作。')
      throw new ApiError(response.status, `服务请求失败（${response.status}）。`)
    }
    return response
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await this.request(path, init)
    return JSON.parse(await boundedText(response)) as T
  }

  catalog(): Promise<Catalog> {
    return this.json('/api/v1/catalog')
  }

  createSession(applicationId: string, caseId: string): Promise<CreatedSession> {
    return this.json('/api/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({ application_id: applicationId, mode: 'scripted-demo', case_id: caseId }),
    })
  }

  submitTurn(sessionId: string, instruction: string, key: string): Promise<{
    session_id: string; ordinal: number; state: string
  }> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/turns`, {
      method: 'POST', body: JSON.stringify({ instruction }),
      headers: { 'Idempotency-Key': key },
    })
  }

  close(sessionId: string, key: string): Promise<{ session_id: string; state: string }> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/close`, {
      method: 'POST', headers: { 'Idempotency-Key': key },
    })
  }

  status(sessionId: string): Promise<SessionStatus> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}`)
  }

  turn(sessionId: string, ordinal: number): Promise<CommittedTurn> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/turns/${ordinal}`)
  }

  result(sessionId: string): Promise<unknown> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/result`)
  }

  evidence(sessionId: string, ref: string): Promise<unknown> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/evidence?ref=${encodeURIComponent(ref)}`)
  }

  async report(sessionId: string): Promise<string> {
    const response = await this.request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/report`)
    return boundedText(response)
  }

  async *events(sessionId: string, after: number, signal: AbortSignal): AsyncGenerator<SessionEvent> {
    const response = await this.request(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/events?after=${after}`,
      { signal },
    )
    if (!response.body) throw new Error('事件流不可用')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let cursor = after
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        if (buffer.length > MAX_EVENT_BYTES) throw new Error('事件帧超过允许大小')
        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          const data = frame.split('\n').find((line) => line.startsWith('data: '))
          if (!data) continue
          const event = JSON.parse(data.slice(6)) as SessionEvent
          if (!Number.isSafeInteger(event.sequence) || event.sequence <= cursor) continue
          if (event.schema !== 'capstone-session-event/1.0' || event.session_id !== sessionId) {
            throw new Error('事件身份无效')
          }
          cursor = event.sequence
          yield event
        }
      }
    } finally {
      reader.releaseLock()
    }
  }
}
