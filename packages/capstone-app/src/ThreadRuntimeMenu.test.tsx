import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ThreadRuntimeMenu from './ThreadRuntimeMenu'

afterEach(cleanup)

it('shows only the selected name and supports keyboard selection and dismissal', () => {
  const change = vi.fn()
  render(<ThreadRuntimeMenu value="capstone" disabled={false} onChange={change} />)
  const trigger = screen.getByRole('button', { name: '运行模式' })
  expect(trigger.textContent).toBe('Capstone')
  fireEvent.keyDown(trigger, { key: 'ArrowDown' })
  const current = screen.getByRole('menuitemradio', { name: 'Capstone' })
  const general = screen.getByRole('menuitemradio', { name: 'Pi' })
  expect(current.getAttribute('aria-checked')).toBe('true')
  expect(document.activeElement).toBe(current)
  fireEvent.keyDown(current, { key: 'ArrowDown' })
  expect(document.activeElement).toBe(general)
  fireEvent.click(general)
  expect(change).toHaveBeenCalledWith('pi_reference')
  expect(screen.queryByRole('menu')).toBeNull()
  expect(document.activeElement).toBe(trigger)
  fireEvent.click(trigger)
  fireEvent.keyDown(screen.getByRole('menuitemradio', { name: 'Capstone' }), { key: 'Escape' })
  expect(screen.queryByRole('menu')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})

it('closes when disabled or clicking outside without changing the mode', () => {
  const change = vi.fn()
  const view = render(<ThreadRuntimeMenu value="pi_reference" disabled={false} onChange={change} />)
  const trigger = screen.getByRole('button', { name: '运行模式' })
  fireEvent.click(trigger)
  fireEvent.pointerDown(document.body)
  expect(screen.queryByRole('menu')).toBeNull()
  fireEvent.click(trigger)
  view.rerender(<ThreadRuntimeMenu value="pi_reference" disabled onChange={change} />)
  expect(screen.queryByRole('menu')).toBeNull()
  expect((trigger as HTMLButtonElement).disabled).toBe(true)
  expect(change).not.toHaveBeenCalled()
})
