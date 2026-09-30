import { parseEventEnvelope, type EventEnvelope } from './threadProtocol'
import type { ThreadCommand, ThreadTransport, ThreadTransportState } from './threadClient'

const MAX_JSON_BYTES = 2 * 1024 * 1024 + 128 * 1024

export class ThreadTransportError extends Error {
  constructor(public readonly status: number, message: string, public readonly body?: unknown) {
    super(message)
    this.name = 'ThreadTransportError'
  }
}

/** HTTP adapter for the future capstone-thread/1 API; it does not own protocol parsing. */
export class HttpThreadTransport implements ThreadTransport {
  readonly connectionState: ThreadTransportState = 'live'
  private readonly base: string
  private readonly resourcePath: string

  constructor(
    baseUrl: string,
    private readonly token: string,
    private readonly fetcher: typeof fetch = fetch,
    resourcePath = '/api/v1/threads',
  ) {
    this.base = baseUrl.trim().replace(/\/$/, '')
    if (this.base && !/^https?:\/\/[^/]+$/.test(this.base)) throw new Error('API 地址无效')
    if (!/^\/[^?]+$/.test(resourcePath)) throw new Error('Thread 资源路径无效')
    this.resourcePath = resourcePath.replace(/\/$/, '')
  }

  private async request(path: string, init: RequestInit = {}): Promise<unknown> {
    const response = await this.fetcher.call(globalThis, this.base + path, {
      ...init,
      credentials: 'omit', cache: 'no-store',
      headers: {
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })
    const text = await response.text()
    if (new TextEncoder().encode(text).byteLength > MAX_JSON_BYTES) throw new Error('Thread 响应超过允许大小')
    let body: unknown = undefined
    try {
      body = JSON.parse(text) as unknown
    } catch {
      if (!response.ok) throw new ThreadTransportError(response.status, `Thread 服务请求失败（${response.status}）。`)
      throw new ThreadTransportError(response.status, 'Thread 响应不是有效 JSON。')
    }
    if (!response.ok) throw new ThreadTransportError(response.status, `Thread 服务请求失败（${response.status}）。`, body)
    return body
  }

  private async streamRequest(path: string, signal?: AbortSignal): Promise<Response> {
    const response = await this.fetcher.call(globalThis, this.base + path, {
      signal, credentials: 'omit', cache: 'no-store',
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : undefined,
    })
    if (!response.ok) {
      const text = await response.text()
      let body: unknown
      try { body = JSON.parse(text) as unknown } catch { body = undefined }
      throw new ThreadTransportError(response.status, `Thread 服务请求失败（${response.status}）。`, body)
    }
    return response
  }

  getSnapshot(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}`, { signal })
  }

  createThread(modelId?: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(this.resourcePath, {
      method: 'POST', signal, body: JSON.stringify(modelId ? { model_id: modelId } : {}),
    })
  }

  readEvents(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/events?after=${afterEventSeq}`, { signal })
  }

  sendCommand(command: ThreadCommand, signal?: AbortSignal): Promise<unknown> {
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
        if (buffer.length > MAX_JSON_BYTES) throw new Error('Thread 事件流超过允许大小')
        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          const data = frame.split('\n').find((line) => line.startsWith('data: '))
          if (!data) continue
          const eventName = frame.split('\n').find((line) => line.startsWith('event: '))?.slice(7)
          const payload = JSON.parse(data.slice(6)) as unknown
          if (eventName === 'resync_required') {
            throw new ThreadTransportError(409, 'Thread SSE requires resync.', payload)
          }
          const event = parseEventEnvelope(payload)
          if (event.threadId !== threadId) throw new Error('Thread 事件身份无效')
          if (event.eventSeq <= cursor) continue
          cursor = event.eventSeq
          yield event
        }
      }
    } finally {
      reader.releaseLock()
    }
  }
}
