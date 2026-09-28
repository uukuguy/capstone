import { describe, expect, it, vi } from 'vitest'
import { ApiError, CapstoneClient } from './api'

describe('CapstoneClient', () => {
  it('loads a demo credential without sending an authorization header', async () => {
    const token = 'public-demo-token-with-enough-length'
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ token })))
    const client = new CapstoneClient('', '', fetcher)
    await expect(client.demoCredential()).resolves.toBe(token)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/demo-credential')
    expect((fetcher.mock.calls[0][1]?.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('retries a transient cold-start response before opening the public demo', async () => {
    vi.useFakeTimers()
    try {
      const token = 'public-demo-token-with-enough-length'
      const fetcher = vi.fn<typeof fetch>()
        .mockResolvedValueOnce(new Response(null, { status: 502 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ token })))
      const client = new CapstoneClient('', '', fetcher)
      const credential = client.demoCredential()
      await vi.runAllTimersAsync()
      await expect(credential).resolves.toBe(token)
      expect(fetcher).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not repeat a mutating request after a transient response', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 502 }))
    const client = new CapstoneClient('', 'demo-token', fetcher)
    await expect(client.createSession('pypsa-business-cases', 'regional-demand-stress'))
      .rejects.toMatchObject({ status: 502 })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

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

  it('sends the creation key when opening a demo run', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      session_id: 'session-0123456789abcdef01234567', run_id: null,
      application_id: 'pypsa-business-cases', state: 'pending',
    }), { status: 201 }))
    const client = new CapstoneClient('', 'demo-token', fetcher)
    await client.createSession('pypsa-business-cases', 'regional-demand-stress', 'create-key')
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toMatchObject({ mode: 'provider' })
    expect((fetcher.mock.calls[0][1]?.headers as Record<string, string>)['Idempotency-Key'])
      .toBe('create-key')
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

  it('reads an authenticated current-run network view for one committed step', async () => {
    const view = { schema: 'capstone-network-view/1.0', ordinal: 2, buses: [], branches: [] }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(view)))
    const client = new CapstoneClient('', 'private-token', fetcher)
    await expect(client.network('session-one', 2)).resolves.toEqual(view)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/sessions/session-one/network?ordinal=2')
    expect((fetcher.mock.calls[0][1]?.headers as Record<string, string>).Authorization)
      .toBe('Bearer private-token')
  })

  it('requests a registered case diagram before a session exists', async () => {
    const diagram = { schema: 'capstone-network-diagram/1.0', buses: [], branches: [] }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(diagram)))
    const client = new CapstoneClient('', 'private-token', fetcher)
    await expect(client.caseDiagram('pypsa-business-cases', 'scigrid-dispatch')).resolves.toEqual(diagram)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/cases/pypsa-business-cases/scigrid-dispatch/diagram')
    expect((fetcher.mock.calls[0][1]?.headers as Record<string, string>).Authorization)
      .toBe('Bearer private-token')
  })
})
