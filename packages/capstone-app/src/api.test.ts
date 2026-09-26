import { describe, expect, it, vi } from 'vitest'
import { ApiError, CapstoneClient } from './api'

describe('CapstoneClient', () => {
  it('keeps the operator token in the authorization header and retries a turn with the same key', async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () =>
      new Response(JSON.stringify({ session_id: 'session-one', ordinal: 1, state: 'accepted' }), {
        status: 202,
        headers: { 'content-type': 'application/json' },
      }),
    )
    const client = new CapstoneClient('', 'private-token', fetcher)
    await client.submitTurn('session-one', 'inspect', 'same-request-key')
    await client.submitTurn('session-one', 'inspect', 'same-request-key')
    expect(fetcher).toHaveBeenCalledTimes(2)
    for (const [url, init] of fetcher.mock.calls) {
      expect(String(url)).not.toContain('private-token')
      expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer private-token')
      expect((init?.headers as Record<string, string>)['Idempotency-Key']).toBe('same-request-key')
    }
  })

  it('parses split SSE frames, skips keepalives, and ignores duplicate cursor IDs', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(': keepalive\n\nid: 2\nevent: ready\ndata: {"schema":"capstone-session-event/1.0","session_id":"session-one","sequence":2,"event":"ready","payload":{}}\n'))
        controller.enqueue(encoder.encode('\nid: 2\nevent: ready\ndata: {"schema":"capstone-session-event/1.0","session_id":"session-one","sequence":2,"event":"ready","payload":{}}\n\nid: 3\nevent: completed\ndata: {"schema":"capstone-session-event/1.0","session_id":"session-one","sequence":3,"event":"completed","payload":{}}\n\n'))
        controller.close()
      },
    })
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(stream, { status: 200 }))
    const client = new CapstoneClient('https://api.example.com', 'private-token', fetcher)
    const events = []
    for await (const event of client.events('session-one', 1, new AbortController().signal)) {
      events.push(event)
    }
    expect(events.map((event) => event.sequence)).toEqual([2, 3])
    expect(fetcher.mock.calls[0][0]).toBe('https://api.example.com/api/v1/sessions/session-one/events?after=1')
  })

  it('reports authorization failure without exposing the credential', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 401 }))
    const client = new CapstoneClient('', 'private-token', fetcher)
    await expect(client.catalog()).rejects.toBeInstanceOf(ApiError)
    await expect(client.catalog()).rejects.toMatchObject({ status: 401 })
  })

  it('calls native-style fetch with the browser global receiver', async () => {
    const browserFetch = vi.fn(function (this: unknown) {
      if (this !== globalThis) throw new TypeError('Illegal invocation')
      return Promise.resolve(new Response(JSON.stringify({ schema: 'capstone-catalog/1.0', applications: [] })))
    }) as unknown as typeof fetch
    const client = new CapstoneClient('', 'private-token', browserFetch)
    await expect(client.catalog()).resolves.toMatchObject({ schema: 'capstone-catalog/1.0' })
  })
})
