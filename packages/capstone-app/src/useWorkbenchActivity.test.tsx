import { act, cleanup, fireEvent, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useWorkbenchActivity } from './useWorkbenchActivity'

afterEach(() => { cleanup(); vi.useRealTimers() })
describe('workbench activity lifecycle', () => {
  it('pauses a page left open and resumes only after preparation succeeds', async () => {
    vi.useFakeTimers()
    let resolve: () => void
    const prepare = vi.fn(() => new Promise<void>(done => { resolve = done }))
    const { result } = renderHook(() => useWorkbenchActivity(prepare, false))
    act(() => vi.advanceTimersByTime(15 * 60 * 1000))
    expect(result.current.paused).toBe(true)
    expect(prepare).not.toHaveBeenCalled()
    fireEvent.pointerMove(window)
    expect(prepare).toHaveBeenCalledTimes(1)
    expect(result.current.mode).toBe('preparing')
    expect(result.current.paused).toBe(true)
    await act(async () => { resolve() })
    expect(result.current.paused).toBe(false)
  })
  it('does not pause an executing task and counts real input as activity', () => {
    vi.useFakeTimers()
    const prepare = vi.fn().mockResolvedValue(undefined)
    const { result, rerender } = renderHook(({ busy }) => useWorkbenchActivity(prepare, busy), { initialProps: { busy: true } })
    act(() => vi.advanceTimersByTime(60 * 60 * 1000))
    expect(result.current.paused).toBe(false)
    rerender({ busy: false })
    act(() => vi.advanceTimersByTime(14 * 60 * 1000))
    fireEvent.keyDown(window, { key: 'a' })
    act(() => vi.advanceTimersByTime(14 * 60 * 1000))
    expect(result.current.paused).toBe(false)
    act(() => vi.advanceTimersByTime(60 * 1000))
    expect(result.current.paused).toBe(true)
  })
  it('keeps commands blocked after failed preparation', async () => {
    vi.useFakeTimers()
    const prepare = vi.fn().mockRejectedValue(new Error('unavailable'))
    const { result } = renderHook(() => useWorkbenchActivity(prepare, false))
    act(() => vi.advanceTimersByTime(15 * 60 * 1000))
    await act(async () => { fireEvent.focus(window) })
    expect(result.current.mode).toBe('failed')
    expect(result.current.paused).toBe(true)
  })
})
