import { describe, expect, it, vi } from 'vitest'
import { HttpThreadTransport, ThreadTransportError } from './threadHttpTransport'

const command = {
  schema: 'capstone-command/1' as const, command_id: 'cmd_1', idempotency_key: 'idem_1',
  thread_id: 'thr_demo_39', run_id: 'run_001', kind: 'cancel_live_attempt', expected_event_seq: 7,
  payload: { attempt_id: 'attempt_004a' },
}

describe('HttpThreadTransport', () => {
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
})
