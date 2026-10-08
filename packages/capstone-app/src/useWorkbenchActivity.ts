import { useCallback, useEffect, useRef, useState } from 'react'
import type { PreparationUpdate } from './workbenchPreparation'

export type PrepareConnection = (signal: AbortSignal, update: (value: PreparationUpdate) => void) => Promise<void>
const IDLE_MS = 15 * 60 * 1000

/** Browser presence is not a lease. Keep task state; release idle subscriptions. */
export function useWorkbenchActivity(prepare: PrepareConnection | undefined, busy: boolean) {
  const [mode, setMode] = useState<'active' | 'idle' | 'preparing' | 'failed'>('active')
  const [updates, setUpdates] = useState<PreparationUpdate[]>([])
  const [error, setError] = useState<string | null>(null)
  const modeRef = useRef(mode)
  const lastActivity = useRef(Date.now())
  const generation = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const pending = useRef<Promise<void> | null>(null)
  const mounted = useRef(true)
  const resumeFocus = useRef<HTMLElement | null>(null)
  const changeMode = useCallback((value: typeof mode) => {
    modeRef.current = value
    if (mounted.current) setMode(value)
  }, [])
  const ensureReady = useCallback((): Promise<void> => {
    if (!prepare || modeRef.current === 'active') return Promise.resolve()
    if (pending.current) return pending.current
    const current = ++generation.current
    const abort = new AbortController()
    abortRef.current = abort
    const timeout = setTimeout(() => abort.abort(), 180000)
    changeMode('preparing'); setError(null)
    setUpdates([{ component: 'api', status: 'preparing' }])
    const request = (async () => {
      try {
        await prepare(abort.signal, value => {
          if (mounted.current && current === generation.current) setUpdates(before =>
            before.some(item => item.component === value.component)
              ? before.map(item => item.component === value.component ? value : item) : [...before, value])
        })
        abort.signal.throwIfAborted()
        if (mounted.current && current === generation.current) {
          lastActivity.current = Date.now(); changeMode('active')
        }
      } catch (cause) {
        if (mounted.current && current === generation.current) {
          setError('暂时无法恢复连接，请重试。'); changeMode('failed')
        }
        throw cause
      } finally {
        clearTimeout(timeout)
        if (current === generation.current) pending.current = null
      }
    })()
    pending.current = request
    return request
  }, [prepare, changeMode])
  useEffect(() => {
    if (mode === 'active' && resumeFocus.current?.isConnected && document.activeElement === document.body) {
      resumeFocus.current.focus({ preventScroll: true })
    }
  }, [mode])
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; generation.current++; abortRef.current?.abort() }
  }, [])
  useEffect(() => {
    if (!prepare) return
    let timer: ReturnType<typeof setTimeout> | undefined
    const suspend = () => {
      resumeFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
      generation.current++; abortRef.current?.abort(); pending.current = null; changeMode('idle')
    }
    const activity = () => {
      lastActivity.current = Date.now()
      if (modeRef.current === 'idle' && document.visibilityState !== 'hidden') void ensureReady().catch(() => {})
    }
    const visibility = () => {
      if (document.visibilityState === 'hidden') suspend()
      else activity()
    }
    const check = () => {
      if (modeRef.current !== 'active') return
      const remaining = IDLE_MS - (Date.now() - lastActivity.current)
      if (!busy && remaining <= 0) suspend()
      else timer = setTimeout(check, busy ? IDLE_MS : Math.max(1, remaining))
    }
    if (mode === 'active') { lastActivity.current = Date.now(); timer = setTimeout(check, IDLE_MS) }
    const events = ['pointermove', 'pointerdown', 'keydown', 'wheel', 'touchstart', 'focus']
    for (const event of events) window.addEventListener(event, activity, { capture: true, passive: true })
    document.addEventListener('visibilitychange', visibility)
    return () => {
      if (timer) clearTimeout(timer)
      for (const event of events) window.removeEventListener(event, activity, true)
      document.removeEventListener('visibilitychange', visibility)
    }
  }, [prepare, busy, mode, ensureReady, changeMode])
  return { mode, paused: mode !== 'active', updates, error, ensureReady }
}
