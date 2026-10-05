import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadSessionMenu from './ThreadSessionMenu'
import { HttpThreadTransport } from './threadHttpTransport'

afterEach(cleanup)

it('lists, switches, archives and restores Threads through visible controls', async () => {
  let archived = false
  const row = () => ({ thread_id: 'thr_one', model_id: 'ieee39', implementation_family: 'pandapower',
    created_at: '2026-10-06T00:00:00Z', last_event_seq: 5, archived })
  const fetcher = vi.fn<typeof fetch>(async (input, init) => {
    if (init?.method === 'POST') {
      archived = JSON.parse(String(init.body)).archived
      return new Response(JSON.stringify(row()))
    }
    const filter = new URL(String(input), 'http://localhost').searchParams.get('archived') === 'true'
    return new Response(JSON.stringify({ schema: 'capstone-thread-list/1', threads: filter === archived ? [row()] : [],
      next_before_thread_id: null, has_more: false }))
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
  fireEvent.click(await screen.findByRole('button', { name: /ieee39/ }))
  expect(select).toHaveBeenCalledWith('thr_one')
})
