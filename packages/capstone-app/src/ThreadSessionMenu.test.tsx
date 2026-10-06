import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadSessionMenu from './ThreadSessionMenu'
import { HttpThreadTransport } from './threadHttpTransport'

afterEach(() => { cleanup(); localStorage.clear() })

it('lists, switches, archives and restores Threads through visible controls', async () => {
  let archived = false
  const row = () => ({ thread_id: 'thr_one', model_id: 'ieee39', implementation_family: 'pandapower',
    created_at: '2026-10-06T00:00:00Z', last_event_seq: 5, archived, title: 'IEEE-39 潮流分析' })
  const fetcher = vi.fn<typeof fetch>(async (input, init) => {
    if (init?.method === 'POST') {
      archived = JSON.parse(String(init.body)).archived
      return new Response(JSON.stringify(row()))
    }
    const query = new URL(String(input), 'http://localhost').searchParams
    expect(query.get('current_thread_id')).toBe('thr_one')
    const filter = query.get('archived') === 'true'
    return new Response(JSON.stringify({ schema: 'capstone-thread-list/1', threads: filter === archived ? [row()] : [], next_before_thread_id: null, has_more: false }))
  })
  const select = vi.fn(); const archive = vi.fn()
  render(<ThreadSessionMenu transport={new HttpThreadTransport('', 'private-token', fetcher)} threadId="thr_one"
    creating={false} onNew={vi.fn()} onSelect={select} onArchived={archive} />)
  fireEvent.click(screen.getByRole('button', { name: '会话列表' }))
  fireEvent.click(await screen.findByRole('button', { name: '归档 thr_one' }))
  await waitFor(() => expect(archive).toHaveBeenCalledWith(true))
  fireEvent.click(screen.getByRole('button', { name: '已归档' }))
  fireEvent.click(await screen.findByRole('button', { name: '恢复 thr_one' }))
  await waitFor(() => expect(archive).toHaveBeenCalledWith(false))
  fireEvent.click(screen.getByRole('button', { name: '最近对话' }))
  fireEvent.click(await screen.findByRole('button', { name: /IEEE-39 潮流分析/ }))
  expect(select).toHaveBeenCalledWith('thr_one')
})

it('requests the active Thread user scope and closes with Escape', async () => {
  const fetcher = vi.fn<typeof fetch>(async (input) => {
    expect(new URL(String(input), 'http://localhost').searchParams.get('current_thread_id')).toBe('thr_mine')
    return new Response(JSON.stringify({ schema: 'capstone-thread-list/1', threads: [{ thread_id: 'thr_mine', model_id: 'two-bus', implementation_family: 'pypsa',
      created_at: '2026-10-06T00:00:00Z', last_event_seq: 5, archived: false, title: '经济调度与潮流校验' }], next_before_thread_id: null, has_more: false }))
  })
  render(<ThreadSessionMenu transport={new HttpThreadTransport('', '', fetcher)} threadId="thr_mine" creating={false} onNew={vi.fn()} onSelect={vi.fn()} onArchived={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '会话列表' }))
  expect(await screen.findByText('经济调度与潮流校验')).toBeTruthy()
  expect(screen.getByText('我的对话')).toBeTruthy()
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('region', { name: '会话列表' })).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '会话列表' }))
})

it('keeps the accepted archive change in sync when the panel closes during submission', async () => {
  const row = { thread_id: 'thr_pending', model_id: 'ieee39', implementation_family: 'pandapower', created_at: '2026-10-06T00:00:00Z', last_event_seq: 0, archived: false }
  let finish: () => void = () => {}
  const fetcher = vi.fn<typeof fetch>(async (_input, init) => {
    if (init?.method === 'POST') {
      await new Promise<void>((resolve) => { finish = resolve })
      if (init.signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return new Response(JSON.stringify({ ...row, archived: true }))
    }
    return new Response(JSON.stringify({ schema: 'capstone-thread-list/1', threads: [row], next_before_thread_id: null, has_more: false }))
  })
  const onArchived = vi.fn()
  render(<ThreadSessionMenu transport={new HttpThreadTransport('', '', fetcher)} threadId="thr_pending" creating={false} onNew={vi.fn()} onSelect={vi.fn()} onArchived={onArchived} />)
  fireEvent.click(screen.getByRole('button', { name: '会话列表' }))
  fireEvent.click(await screen.findByRole('button', { name: '归档 thr_pending' }))
  fireEvent.keyDown(document, { key: 'Escape' })
  finish()
  await waitFor(() => expect(onArchived).toHaveBeenCalledWith(true))
})
