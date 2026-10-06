export type ThreadAccessMode = 'open' | 'operator'

export async function readThreadAccess(apiOrigin: string, signal: AbortSignal): Promise<ThreadAccessMode> {
  const response = await fetch(`${apiOrigin.replace(/\/$/, '')}/api/v1/thread-access`, {
    signal, credentials: 'omit', cache: 'no-store',
  })
  // Earlier hosts expose only the operator-authenticated Thread API.
  if (response.status === 401 || response.status === 404) return 'operator'
  if (!response.ok) throw new Error('工作台服务暂不可用，请重试。')
  const body: unknown = await response.json()
  if (!body || typeof body !== 'object' || !('schema' in body)
      || body.schema !== 'capstone-thread-access/1' || !('mode' in body)
      || (body.mode !== 'open' && body.mode !== 'operator')) {
    throw new Error('工作台连接配置无效，请重试。')
  }
  return body.mode
}
