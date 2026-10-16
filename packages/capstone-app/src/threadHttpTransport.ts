import { parseEventEnvelope, type EventEnvelope } from './threadProtocol'
import type { ThreadCommand, ThreadTransport, ThreadTransportState } from './threadClient'
import { MAX_THREAD_JSON_BYTES } from './networkLimits'
import { parseThreadDescriptor, parseThreadListPage } from './threadManagement'
import { fetchWithReadRetry } from './httpRetry'
import { parseAttemptRecords } from './attemptRecords'
import type { WorkCommand } from './threadWorkProtocol'

const MAX_JSON_BYTES = MAX_THREAD_JSON_BYTES
const THREAD_VERSION_HEADER = 'Capstone-Thread-Version'
const THREAD_VERSION = '1'
const VERSION_ERRORS = new Set(['unsupported_thread_version', 'protocol_upgrade_required', 'thread_version_mismatch'])

function versionError(body: unknown): boolean {
  return !!body && typeof body === 'object' && 'error' in body
    && typeof body.error === 'string' && VERSION_ERRORS.has(body.error)
}

export class ThreadTransportError extends Error {
  constructor(public readonly status: number, message: string, public readonly body?: unknown) {
    super(message)
    this.name = 'ThreadTransportError'
  }
}

export function isThreadVersionError(error: unknown): error is ThreadTransportError {
  return error instanceof ThreadTransportError && versionError(error.body)
}

function responseError(status: number, body?: unknown): ThreadTransportError {
  return new ThreadTransportError(status, versionError(body)
    ? '应用与会话协议版本不兼容，请更新应用后重新打开会话。'
    : `Thread 服务请求失败（${status}）。`, body)
}

async function checkResponseVersion(response: Response, requestedVersion = THREAD_VERSION): Promise<void> {
  const version = response.headers.get(THREAD_VERSION_HEADER)
  // Older v1 servers do not echo a version. Their strict body parsers still apply.
  if (response.ok && ((version !== null && version !== requestedVersion) || (requestedVersion === '2' && version === null))) {
    await response.body?.cancel().catch(() => undefined)
    throw responseError(409, { error: 'thread_version_mismatch' })
  }
}

/** HTTP adapter for the negotiated Thread API; payload parsing remains in the client. */
export class HttpThreadTransport implements ThreadTransport {
  readonly connectionState: ThreadTransportState = 'live'
  private readonly base: string
  private readonly resourcePath: string
  // Missing request headers mean v1. Wait for a visible server advertisement
  // before adding a custom header that older cross-origin servers cannot allow.
  // Never retry a write to discover protocol support.
  private versionAdvertised = false

  constructor(
    baseUrl: string,
    private readonly token: string,
    private readonly fetcher: typeof fetch = fetch,
    resourcePath = '/api/v1/threads',
    private readonly protocolVersion: '1' | '2' = '1',
  ) {
    this.base = baseUrl.trim().replace(/\/$/, '')
    if (this.base && !/^https?:\/\/[^/]+$/.test(this.base)) throw new Error('API 地址无效')
    if (!/^\/[^?]+$/.test(resourcePath)) throw new Error('Thread 资源路径无效')
    this.resourcePath = resourcePath.replace(/\/$/, '')
  }

  private async request(path: string, init: RequestInit = {}): Promise<unknown> {
    const response = await fetchWithReadRetry(this.base + path, {
      ...init,
      credentials: 'omit', cache: 'no-store',
      headers: {
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
        ...(this.versionAdvertised || this.protocolVersion === '2' ? { [THREAD_VERSION_HEADER]: this.protocolVersion } : {}),
      },
    }, this.fetcher)
    await checkResponseVersion(response, this.protocolVersion)
    this.versionAdvertised = response.ok && response.headers.get(THREAD_VERSION_HEADER) === this.protocolVersion
    const text = await response.text()
    if (new TextEncoder().encode(text).byteLength > MAX_JSON_BYTES) throw new Error('Thread 响应超过允许大小')
    let body: unknown = undefined
    try {
      body = JSON.parse(text) as unknown
    } catch {
      if (!response.ok) throw new ThreadTransportError(response.status, `Thread 服务请求失败（${response.status}）。`)
      throw new ThreadTransportError(response.status, 'Thread 响应不是有效 JSON。')
    }
    if (!response.ok) throw responseError(response.status, body)
    return body
  }

  private async streamRequest(path: string, signal?: AbortSignal): Promise<Response> {
    const response = await fetchWithReadRetry(this.base + path, {
      signal, credentials: 'omit', cache: 'no-store',
      headers: { ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(this.versionAdvertised || this.protocolVersion === '2' ? { [THREAD_VERSION_HEADER]: this.protocolVersion } : {}) },
    }, this.fetcher)
    await checkResponseVersion(response, this.protocolVersion)
    this.versionAdvertised = response.ok && response.headers.get(THREAD_VERSION_HEADER) === this.protocolVersion
    if (!response.ok) {
      const text = await response.text()
      let body: unknown
      try { body = JSON.parse(text) as unknown } catch { body = undefined }
      throw responseError(response.status, body)
    }
    return response
  }

  getSnapshot(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}`, { signal })
  }

  getInputCatalog(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/input-catalog`, { signal })
  }

  readHistory(threadId: string, beforeEventSeq?: number, signal?: AbortSignal): Promise<unknown> {
    const query = new URLSearchParams({ limit: '128' })
    if (beforeEventSeq !== undefined) query.set('before', String(beforeEventSeq))
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/history?${query}`, { signal })
  }

  async readAttemptRecords(threadId: string, attemptId: string, after = 0, signal?: AbortSignal) {
    if (!Number.isSafeInteger(after) || after < 0) throw new Error('任务记录游标无效')
    const query = new URLSearchParams({ after: String(after), limit: '32' })
    const body = await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/attempts/${encodeURIComponent(attemptId)}/records?${query}`, { signal })
    return parseAttemptRecords(body, threadId, attemptId, after)
  }

  readNetworkEvents(threadId: string, signal?: AbortSignal, contextId?: string, attemptId?: string): Promise<unknown> {
    const query = new URLSearchParams()
    if (contextId) query.set('context_id', contextId)
    if (attemptId) query.set('attempt_id', attemptId)
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/network-events${query.size ? `?${query}` : ''}`, { signal })
  }

  async getModels(threadId: string, signal?: AbortSignal): Promise<unknown> {
    try { return await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/models`, { signal }) }
    catch (cause) { if (cause instanceof ThreadTransportError && cause.status === 404) return null; throw cause }
  }

  async listThreads(archived = false, before?: string, signal?: AbortSignal) {
    const query = new URLSearchParams({ archived: String(archived), limit: '20' })
    if (before) query.set('before', before)
    return parseThreadListPage(await this.request(`${this.resourcePath}?${query}`, { signal }))
  }

  async archiveThread(threadId: string, archived: boolean, signal?: AbortSignal) {
    return parseThreadDescriptor(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/archive`, {
      method: 'POST', signal, body: JSON.stringify({ archived }),
    }))
  }

  async getThreadMetadata(threadId: string, signal?: AbortSignal): Promise<{ archived: boolean }> {
    const body = await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/metadata`, { signal })
    if (!body || typeof body !== 'object' || !('archived' in body) || typeof body.archived !== 'boolean') throw new Error('会话状态无效')
    return { archived: body.archived }
  }

  getCatalog(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/catalog`, { signal })
  }

  createThread(modelId?: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(this.resourcePath, {
      method: 'POST', signal, body: JSON.stringify(modelId ? { model_id: modelId } : {}),
    })
  }

  createWorkThread(signal?: AbortSignal): Promise<unknown> {
    if (this.protocolVersion !== '2') throw new Error('工作会话需要新版协议')
    return this.request(this.resourcePath, { method: 'POST', signal, body: JSON.stringify({}) })
  }

  readEvents(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/events?after=${afterEventSeq}`, { signal })
  }

  sendCommand(command: ThreadCommand | WorkCommand, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(command.thread_id)}/commands`, {
      method: 'POST', signal, body: JSON.stringify(command),
      headers: { 'Idempotency-Key': command.idempotency_key },
    })
  }

  async *streamEvents(
    threadId: string, afterEventSeq: number, signal?: AbortSignal,
  ): AsyncGenerator<EventEnvelope> {
    const response = await this.streamRequest(
      `${this.resourcePath}/${encodeURIComponent(threadId)}/events/stream?after=${afterEventSeq}&follow=1`,
      signal,
    )
    if (!response.body) throw new Error('Thread 事件流不可用')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let cursor = afterEventSeq
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          if (new TextEncoder().encode(frame).byteLength > MAX_JSON_BYTES) throw new Error('Thread 事件流超过允许大小')
          const data = frame.split('\n').find((line) => line.startsWith('data: '))
          if (!data) continue
          const eventName = frame.split('\n').find((line) => line.startsWith('event: '))?.slice(7)
          const payload = JSON.parse(data.slice(6)) as unknown
          if (eventName === 'protocol_upgrade_required') throw responseError(409, payload)
          if (eventName === 'resync_required') {
            throw new ThreadTransportError(409, 'Thread SSE requires resync.', payload)
          }
          const event = parseEventEnvelope(payload)
          if (event.threadId !== threadId) throw new Error('Thread 事件身份无效')
          if (event.eventSeq <= cursor) continue
          cursor = event.eventSeq
          yield event
        }
        if (new TextEncoder().encode(buffer).byteLength > MAX_JSON_BYTES) throw new Error('Thread 事件流超过允许大小')
      }
    } finally {
      await reader.cancel().catch(() => undefined)
      reader.releaseLock()
    }
  }
}
