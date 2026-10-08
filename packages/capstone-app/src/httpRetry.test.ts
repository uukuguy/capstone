import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchWithReadRetry } from './httpRetry'

afterEach(() => vi.useRealTimers())
describe('cold-start read recovery', () => {
  it('recovers from network and gateway cold starts', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fetcher = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce(new Response('', { status: 503 }))
      .mockResolvedValueOnce(new Response('ready'))
    const pending = fetchWithReadRetry('/read', {}, fetcher)
    await vi.runAllTimersAsync()
    expect(await (await pending).text()).toBe('ready')
    expect(fetcher).toHaveBeenCalledTimes(3)
  })
  it.each([401, 403, 404, 409, 500])('does not retry a non-cold-start error %s', async status => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status }))
    expect((await fetchWithReadRetry('/read', {}, fetcher)).status).toBe(status)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('does not replay a write after a gateway error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status: 503 }))
    expect((await fetchWithReadRetry('/write', { method: 'POST' }, fetcher)).status).toBe(503)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('stops retrying on abort', async () => {
    const controller = new AbortController()
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status: 502 }))
    const pending = fetchWithReadRetry('/read', { signal: controller.signal }, fetcher)
    await Promise.resolve()
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
