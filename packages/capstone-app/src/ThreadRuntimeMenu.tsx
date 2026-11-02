import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import type { RuntimeMode } from './threadProtocol'

const modes: { value: RuntimeMode; label: string }[] = [
  { value: 'capstone', label: 'Capstone' },
  { value: 'pi_reference', label: 'Pi' },
]

export default function ThreadRuntimeMenu({ value, disabled, onChange }: {
  value: RuntimeMode; disabled: boolean; onChange: (mode: RuntimeMode) => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const options = useRef<(HTMLButtonElement | null)[]>([])
  const panelId = useId()
  const selected = modes.findIndex((mode) => mode.value === value)
  function close() { setOpen(false); trigger.current?.focus({ preventScroll: true }) }
  useEffect(() => {
    if (disabled) setOpen(false)
  }, [disabled])
  useEffect(() => {
    if (!open) return
    options.current[selected]?.focus({ preventScroll: true })
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open, selected])

  return <div ref={root} className="thread-settings-menu thread-runtime-menu" onBlur={(event) => {
    if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }} onKeyDown={(event) => {
    if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); close(); return }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) || disabled) return
    event.preventDefault(); event.stopPropagation()
    if (!open) { setOpen(true); return }
    const current = options.current.findIndex((option) => option === document.activeElement)
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? modes.length - 1 :
      (current + (event.key === 'ArrowDown' ? 1 : -1) + modes.length) % modes.length
    options.current[next]?.focus()
  }}>
    <button ref={trigger} type="button" className="thread-settings-trigger" aria-label="运行模式"
      title="切换对话模式" aria-haspopup="menu" aria-expanded={open && !disabled} aria-controls={panelId}
      disabled={disabled} onClick={() => setOpen(!open)}>
      <span>{modes[selected].label}</span><ChevronDown aria-hidden="true" />
    </button>
    {open && !disabled && <div id={panelId} className="thread-settings-popover thread-runtime-panel" role="menu" aria-label="运行模式">
      {modes.map((mode, index) => <div key={mode.value} className="thread-opened-row" role="presentation">
        <button ref={(element) => { options.current[index] = element }} type="button" role="menuitemradio" tabIndex={-1}
          aria-checked={mode.value === value} className="thread-opened-select thread-runtime-option"
          onClick={() => { close(); if (mode.value !== value) onChange(mode.value) }}>
          <span className="thread-opened-check">{mode.value === value && <Check aria-hidden="true" />}</span>
          <span>{mode.label}</span>
        </button>
      </div>)}
    </div>}
  </div>
}
