import { fetchWithReadRetry } from './httpRetry'

export type PreparationStatus = 'waiting' | 'preparing' | 'ready' | 'failed'
export type PreparationUpdate = { component: string; status: PreparationStatus }

/** Bounded, public readiness projections. No command is sent during startup. */
export async function prepareWorkbench(origin: string, signal: AbortSignal,
                                       update: (value: PreparationUpdate) => void): Promise<void> {
  const response = await fetchWithReadRetry(`${origin.replace(/\/$/, '')}/api/v1/workbench-preparation`, {
    signal, credentials: 'omit', cache: 'no-store',
  }, fetch, 32)
  // Older hosts keep their existing access bootstrap.
  if (response.status === 401 || response.status === 404) return
  if (!response.ok || !response.body) throw new Error('工作台暂未就绪，请重试。')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let bytes = 0
  const states = new Map<string, PreparationStatus>()
  try {
    while (true) {
      const part = await reader.read()
      if (part.done) break
      bytes += part.value.byteLength
      if (bytes > 64 * 1024) throw new Error('准备状态超过允许大小')
      buffer += decoder.decode(part.value, { stream: true })
      let boundary: number
      while ((boundary = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 1)
        if (!line.trim()) continue
        const frame: unknown = JSON.parse(line)
        if (!frame || typeof frame !== 'object' || !('schema' in frame)
            || frame.schema !== 'capstone-workbench-preparation/1'
            || !('component' in frame) || typeof frame.component !== 'string'
            || !/^(api|database|workbench|worker(?::[a-z][a-z0-9_-]{0,63})?)$/.test(frame.component)
            || !('status' in frame) || !['preparing', 'ready', 'failed'].includes(String(frame.status))) {
          throw new Error('准备状态无效，请重试。')
        }
        const status = frame.status as PreparationStatus
        if (frame.component !== 'workbench') {
          states.set(frame.component, status)
          if (states.size > 16) throw new Error('准备状态超过允许大小')
          update({ component: frame.component, status })
        }
        if (status === 'failed') throw new Error('部分服务暂未就绪，请重试。')
        if ('complete' in frame && frame.complete === true) {
          if (frame.component !== 'workbench' || status !== 'ready'
              || states.get('api') !== 'ready' || states.get('database') !== 'ready'
              || [...states.values()].some(value => value !== 'ready')) {
            throw new Error('工作台暂未就绪，请重试。')
          }
          return
        }
      }
    }
    throw new Error('准备连接中断，请重试。')
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
