import type { ThreadCommand, ThreadTransport, ThreadTransportState } from './threadClient'

const MAX_JSON_BYTES = 2 * 1024 * 1024 + 128 * 1024

export class ThreadTransportError extends Error {
  constructor(public readonly status: number, message: string) {
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
    if (!response.ok) throw new ThreadTransportError(response.status, `Thread 服务请求失败（${response.status}）。`)
    const text = await response.text()
    if (new TextEncoder().encode(text).byteLength > MAX_JSON_BYTES) throw new Error('Thread 响应超过允许大小')
    try {
      return JSON.parse(text) as unknown
    } catch {
      throw new ThreadTransportError(response.status, 'Thread 响应不是有效 JSON。')
    }
  }

  getSnapshot(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}`, { signal })
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
}
