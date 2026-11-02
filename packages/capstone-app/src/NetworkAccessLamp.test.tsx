import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import NetworkAccessLamp from './NetworkAccessLamp'

afterEach(cleanup)

test('changes colour only after the backend confirms the switch', async () => {
  let confirm!: (value: Response) => void
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({external_access:false,enforced:true})))
    .mockImplementationOnce(()=>new Promise<Response>(resolve=>{confirm=resolve}))
  render(<NetworkAccessLamp fetcher={fetcher} />)
  const button = await screen.findByRole('switch', {name:/外网已关闭/})
  fireEvent.click(button)
  expect(button.getAttribute('aria-checked')).toBe('false')
  expect(button.getAttribute('aria-busy')).toBe('true')
  confirm(new Response(JSON.stringify({external_access:true,enforced:true})))
  await waitFor(()=>expect(button.getAttribute('aria-checked')).toBe('true'))
})

test('unavailable backend is shown as unknown, not confirmed closed', async () => {
  const fetcher = vi.fn().mockRejectedValue(new Error('offline'))
  render(<NetworkAccessLamp fetcher={fetcher} />)
  await screen.findByRole('switch', {name:/外网状态暂不可用/})
  expect(screen.queryByRole('switch', {name:/外网已关闭/})).toBeNull()
})
