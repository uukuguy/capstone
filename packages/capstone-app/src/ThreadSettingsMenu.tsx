import { createContext, useContext, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, Settings2 } from 'lucide-react'

const CloseSettingsContext = createContext<() => void>(() => {})
export const useCloseThreadSettings = () => useContext(CloseSettingsContext)

/** One presentation entry shared by the real App and isolated Thread views. */
export default function ThreadSettingsMenu({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [availableHeight, setAvailableHeight] = useState<number>()
  const panelId = useId()
  function close() { setOpen(false); trigger.current?.focus({ preventScroll: true }) }
  useLayoutEffect(() => {
    if (!open) return
    const measure = () => {
      const rect = trigger.current?.getBoundingClientRect()
      if (!rect?.height) return
      const boundary = root.current?.closest('.capstone-assistant-thread')?.getBoundingClientRect().top || 0
      setAvailableHeight(Math.max(0, rect.top - Math.max(8, boundary + 8) - 8))
    }
    measure()
    window.addEventListener('resize', measure)
    document.addEventListener('scroll', measure, true)
    return () => { window.removeEventListener('resize', measure); document.removeEventListener('scroll', measure, true) }
  }, [open])
  useEffect(() => {
    if (!open) return
    const outside = (event: Event) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    document.addEventListener('click', outside, true)
    document.addEventListener('pointerdown', outside, true)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('click', outside, true); document.removeEventListener('pointerdown', outside, true); document.removeEventListener('keydown', escape) }
  }, [open])
  return <div ref={root} className={`thread-settings-menu${open ? ' is-open' : ''}`} onBlur={(event) => {
    if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    <button ref={trigger} type="button" className="thread-settings-trigger" aria-label="对话设置" title="对话设置" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}><Settings2 aria-hidden="true" /><span>设置</span><ChevronDown aria-hidden="true" /></button>
    {open && <CloseSettingsContext.Provider value={close}><div id={panelId} className="thread-settings-popover" role="group" aria-label="对话设置" style={{ maxHeight: availableHeight }}>{children}</div></CloseSettingsContext.Provider>}
  </div>
}
