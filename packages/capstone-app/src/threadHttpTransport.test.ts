import { describe, expect, it, vi } from 'vitest'
import { HttpThreadTransport, ThreadTransportError } from './threadHttpTransport'
import { MAX_THREAD_JSON_BYTES } from './networkLimits'
import { sampleDiagramView } from './networkFixture'

const command = {
  schema: 'capstone-command/1' as const, command_id: 'cmd_1', idempotency_key: 'idem_1',
  thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'cancel_live_attempt', expected_event_seq: 7,
  payload: { attempt_id: 'attempt_004a' },
}

describe('HttpThreadTransport', () => {
  it('bounds each SSE frame rather than a chunk containing multiple complete diagrams', async () => {
    const buses = Array.from({ length: 10000 }, (_, i) => ({
      id: String(i), label: 'x'.repeat(200), x: null, y: null, vn_kv: 220,
    }))
    const frame = (seq: number) => `data: ${JSON.stringify({
      event_id: `evt_${seq}`, event_seq: seq, event_type: 'network_diagram', event_version: 1,
      thread_id: 'thr_demo_39', run_id: 'run_001', occurred_at: '2026-09-30T00:00:00Z',
      visibility: 'public', payload: { diagram: { ...sampleDiagramView.diagram,
        coordinate_system: 'schematic', buses, branches: [] } },
    })}\n\n`
    const bytes = new TextEncoder().encode(frame(1) + frame(2))
    const stream = new ReadableStream<Uint8Array>({ start(controller) { controller.enqueue(bytes); controller.close() } })
    const transport = new HttpThreadTransport('', '', vi.fn<typeof fetch>().mockResolvedValue(new Response(stream)))
    const sequences = []
    for await (const event of transport.streamEvents('thr_demo_39', 0)) sequences.push(event.eventSeq)
    expect(sequences).toEqual([1, 2])
    const oversized = new HttpThreadTransport('', '', vi.fn<typeof fetch>().mockResolvedValue(new Response('x'.repeat(MAX_THREAD_JSON_BYTES + 1))))
    await expect(oversized.getSnapshot('thr_demo_39')).rejects.toThrow('超过允许大小')
  })
  it('reads a snapshot and event page through the configured Thread resource', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ snapshot: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ events: true }), { status: 200 }))
    const transport = new HttpThreadTransport('https://api.example.com/', 'token-1', fetcher)

    await expect(transport.getSnapshot('thr_demo_39')).resolves.toEqual({ snapshot: true })
    await expect(transport.readEvents('thr_demo_39', 7)).resolves.toEqual({ events: true })
    expect(fetcher.mock.calls[0][0]).toBe('https://api.example.com/api/v1/threads/thr_demo_39')
    expect(fetcher.mock.calls[1][0]).toBe('https://api.example.com/api/v1/threads/thr_demo_39/events?after=7')
    expect(fetcher.mock.calls[0][1]).toMatchObject({ credentials: 'omit', cache: 'no-store' })
    expect((fetcher.mock.calls[0][1]?.headers as Record<string, string>).Authorization).toBe('Bearer token-1')
  })

  it('reads the bounded Thread control catalog from the Thread resource', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify({ catalog: true }), { status: 200 }))
    const transport = new HttpThreadTransport('https://api.example.com/', 'token-1', fetcher)

    await expect(transport.getCatalog('thr_demo_39')).resolves.toEqual({ catalog: true })
    expect(fetcher).toHaveBeenCalledWith('https://api.example.com/api/v1/threads/thr_demo_39/catalog', expect.objectContaining({ credentials: 'omit' }))
  })

  it('creates a Thread through the same resource root', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify({
      schema: 'capstone-thread-snapshot/1', thread_id: 'thr_new',
    }), { status: 201 }))
    const transport = new HttpThreadTransport('', 'token-1', fetcher)

    await expect(transport.createThread?.()).resolves.toEqual({
      schema: 'capstone-thread-snapshot/1', thread_id: 'thr_new',
    })
    expect(fetcher).toHaveBeenCalledWith('/api/v1/threads', expect.objectContaining({
      method: 'POST', body: '{}',
    }))
  })

  it('posts commands with the original idempotency key and bounded JSON payload', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ accepted: true }), { status: 200 }))
    const transport = new HttpThreadTransport('', 'token-1', fetcher)

    await expect(transport.sendCommand(command)).resolves.toEqual({ accepted: true })
    expect(fetcher).toHaveBeenCalledWith('/api/v1/threads/thr_demo_39/commands', expect.objectContaining({
      method: 'POST', body: JSON.stringify(command),
    }))
    const headers = fetcher.mock.calls[0][1]?.headers as Record<string, string>
    expect(headers['Idempotency-Key']).toBe('idem_1')
    expect(headers['Content-Type']).toBe('application/json')
  })

  it('surfaces non-success responses without treating them as receipts', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      error: 'resync_required', base_event_seq: 3, snapshot: { schema: 'capstone-thread-snapshot/1' },
    }), { status: 409 }))
    const transport = new HttpThreadTransport('', '', fetcher)

    await expect(transport.sendCommand(command)).rejects.toMatchObject({
      status: 409, body: { error: 'resync_required', base_event_seq: 3 },
    })
  })

  it('streams strict Thread events and ignores duplicate SSE cursors', async () => {
    const encoder = new TextEncoder()
    const payload = (sequence: number) => JSON.stringify({
      event_id: `evt_${sequence}`, event_seq: sequence, event_type: 'attempt_progress',
      event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001',
      occurred_at: '2026-09-30T00:00:00Z', visibility: 'public', payload: { phase: 'running' },
    })
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(`: keepalive\n\nid: 2\nevent: attempt_progress\ndata: ${payload(2)}\n\n`))
        controller.enqueue(encoder.encode(`id: 2\nevent: attempt_progress\ndata: ${payload(2)}\n\nid: 3\ndata: ${payload(3)}\n\n`))
        controller.close()
      },
    })
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(stream, { status: 200 }))
    const transport = new HttpThreadTransport('', 'token-1', fetcher)
    const events = []
    for await (const event of transport.streamEvents('thr_demo_39', 1)) events.push(event)

    expect(events.map((item) => item.eventSeq)).toEqual([2, 3])
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/threads/thr_demo_39/events/stream?after=1&follow=1')
  })
})
