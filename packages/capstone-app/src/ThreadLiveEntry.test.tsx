import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import ThreadLiveEntry from './ThreadLiveEntry'

afterEach(() => {
  cleanup()
  sessionStorage.removeItem('capstone.thread.operatorToken')
  vi.unstubAllGlobals()
})

const snapshot = {
  schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo_39',
  run: { run_id: 'run_001', state: 'open' },
  active_model_context: {
    id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: '7',
    implementation_family: 'pandapower', selection_revision: 'sel_2',
  },
  active_grid_page_id: 'page_ieee39', current_attempt: null,
  last_event_seq: 0, base_event_seq: 0,
}

describe('ThreadLiveEntry', () => {
  it('loads a real Thread workspace through HTTP snapshot, page, and SSE adapters', async () => {
    sessionStorage.setItem('capstone.thread.operatorToken', 'private-token')
    vi.stubGlobal('fetch', vi.fn(async (url: string | URL) => {
      if (String(url).includes('/events/stream')) return new Response('', { status: 200 })
      if (String(url).includes('/events?after=')) return new Response(JSON.stringify({
        schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
        after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
      }), { status: 200 })
      return new Response(JSON.stringify(snapshot), { status: 200 })
    }))

    render(<ThreadLiveEntry threadId="thr_demo_39" />)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(screen.getAllByText('pandapower').length).toBeGreaterThan(0)
  })

  it('creates a default IEEE-39 Thread only once under StrictMode', async () => {
    sessionStorage.setItem('capstone.thread.operatorToken', 'private-token')
    const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
      if (String(url) === '/api/v1/threads' && init?.method === 'POST') {
        expect(init.body).toBe(JSON.stringify({ model_id: 'ieee39' }))
        return new Response(JSON.stringify(snapshot), { status: 201 })
      }
      if (String(url).includes('/events/stream')) return new Response('', { status: 200 })
      if (String(url).includes('/events?after=')) return new Response(JSON.stringify({
        schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
        after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
      }), { status: 200 })
      return new Response(JSON.stringify(snapshot), { status: 200 })
    })
    vi.stubGlobal('fetch', fetcher)

    render(<StrictMode><ThreadLiveEntry threadId="new" /></StrictMode>)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(fetcher).toHaveBeenCalledWith('/api/v1/threads', expect.objectContaining({ method: 'POST' }))
    expect(fetcher.mock.calls.filter(([url, init]) => url === '/api/v1/threads' && init?.method === 'POST')).toHaveLength(1)
  })
})
