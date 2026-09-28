import type {
  Catalog, CommittedTurn, CreatedSession, NetworkDiagram, NetworkStory, NetworkView, SessionEvent, SessionStatus,
} from './types'

const MAX_RESPONSE_BYTES = 2 * 1024 * 1024 + 128 * 1024
const MAX_EVENT_BYTES = 2 * 1024 * 1024 + 128 * 1024
const READ_ATTEMPTS = 8

function waitForRetry(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', abort)
      resolve()
    }, ms)
    function abort() {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
  })
}

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
    const options: RequestInit = {
      ...init,
      credentials: 'omit',
      cache: 'no-store',
      headers: {
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    }
    const read = !init.method || init.method.toUpperCase() === 'GET'
    const attempts = read ? READ_ATTEMPTS : 1
    for (let attempt = 0; attempt < attempts; attempt++) {
      let response: Response
      try {
        response = await this.fetcher.call(globalThis, this.base + path, options)
      } catch (cause) {
        if (!read || attempt + 1 === attempts || !(cause instanceof TypeError)) throw cause
        await waitForRetry(Math.min(400 * 2 ** attempt, 2000), init.signal)
        continue
      }
      if (read && [502, 503, 504].includes(response.status) && attempt + 1 < attempts) {
        await waitForRetry(Math.min(400 * 2 ** attempt, 2000), init.signal)
        continue
      }
      if (!response.ok) {
        if (response.status === 401) throw new ApiError(401, '演示连接已失效，请重试连接。')
        if (response.status === 409) throw new ApiError(409, '当前运行状态暂不接受该操作。')
        throw new ApiError(response.status, `服务请求失败（${response.status}）。`)
      }
      return response
    }
    throw new Error('读取请求未完成')
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await this.request(path, init)
    return JSON.parse(await boundedText(response)) as T
  }

  catalog(): Promise<Catalog> {
    return this.json('/api/v1/catalog')
  }

  async demoCredential(): Promise<string> {
    const document = await this.json<unknown>('/api/v1/demo-credential')
    if (!document || typeof document !== 'object' || !('token' in document) ||
        typeof document.token !== 'string' || document.token.length < 32) {
      throw new Error('演示凭证不可用')
    }
    return document.token
  }

  caseDiagram(applicationId: string, caseId: string): Promise<NetworkDiagram> {
    return this.json(`/api/v1/cases/${encodeURIComponent(applicationId)}/${encodeURIComponent(caseId)}/diagram`)
  }

  createSession(applicationId: string, caseId: string,
                key?: string): Promise<CreatedSession> {
    return this.json('/api/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({ application_id: applicationId, mode: 'provider', case_id: caseId }),
      headers: key ? { 'Idempotency-Key': key } : undefined,
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

  disconnect(sessionId: string, key: string): Promise<SessionStatus> {
    return this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/disconnect`, {
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

  async network(sessionId: string, ordinal: number, signal?: AbortSignal): Promise<NetworkView> {
    if (!Number.isSafeInteger(ordinal) || ordinal < 1 || ordinal > 3) {
      throw new Error('电网视图步骤无效')
    }
    const path = `/api/v1/sessions/${encodeURIComponent(sessionId)}/network?ordinal=${ordinal}`
    for (let attempt = 0; attempt < READ_ATTEMPTS; attempt += 1) {
      try {
        return await this.json(path, { signal })
      } catch (cause) {
        const retryable = cause instanceof ApiError && [404, 502, 503, 504].includes(cause.status)
        if (!retryable || attempt + 1 === READ_ATTEMPTS) throw cause
        await waitForRetry(Math.min(300 * 2 ** attempt, 1500), signal)
      }
    }
    throw new Error('电网视图读取未完成')
  }

  async networkStory(sessionId: string, signal?: AbortSignal): Promise<NetworkStory> {
    for (let attempt = 0; attempt < READ_ATTEMPTS; attempt += 1) {
      try {
        return await this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/network-story`, { signal })
      } catch (cause) {
        const retryable = cause instanceof ApiError && [409, 502, 503, 504].includes(cause.status)
        if (!retryable || attempt + 1 === READ_ATTEMPTS) throw cause
        await waitForRetry(Math.min(300 * 2 ** attempt, 1500), signal)
      }
    }
    throw new Error('电气拓扑故事读取未完成')
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
