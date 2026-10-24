import { useEffect, useId, useState, type ReactNode } from 'react'
import { ChevronRight, ChevronsDownUp, ChevronsUpDown } from 'lucide-react'

export type ProcessFoldCommand = { open: boolean; revision: number }
const appliedCommands = new WeakMap<ProcessFoldCommand, Set<string>>()
export function readProcessStepOpen(storageKey: string, id: string, fallback = false): boolean {
  try {
    const value = localStorage.getItem(`capstone-step-open:${storageKey}:${id}`)
    return value === null ? fallback : value === 'true'
  } catch { return fallback }
}
export function saveProcessStepOpen(storageKey: string, id: string, open: boolean): void {
  try { localStorage.setItem(`capstone-step-open:${storageKey}:${id}`, String(open)) } catch { /* Keep the in-memory choice. */ }
}

/** Presentation only: applications supply headings and content without runtime contracts. */
export default function ProcessStepRecord({ id, title, storageKey, heading, children, resultSummary, defaultExpanded = false, foldCommand, onFoldChange, headingClassName = '' }: {
  id: string; title: string; storageKey: string; heading: ReactNode; children: ReactNode; defaultExpanded?: boolean;
  foldCommand?: ProcessFoldCommand; onFoldChange?: (id: string, open: boolean) => void; headingClassName?: string; resultSummary?: string;
}) {
  const bodyId = useId()
  const [open, setOpen] = useState(() => readProcessStepOpen(storageKey, id, defaultExpanded))
  const summary = resultSummary?.replace(/^#{1,6}\s+/gm, '').replace(/\*\*|__|`/g, '').replace(/\s+/g, ' ').trim()
  useEffect(() => {
    if (foldCommand) {
      const key = JSON.stringify([storageKey, id])
      const applied = appliedCommands.get(foldCommand) ?? new Set<string>()
      if (applied.has(key)) return
      applied.add(key); appliedCommands.set(foldCommand, applied)
      setOpen(foldCommand.open)
      saveProcessStepOpen(storageKey, id, foldCommand.open)
    }
  }, [foldCommand, id, storageKey])
  useEffect(() => { onFoldChange?.(id, open) }, [id, open, onFoldChange])
  return <>
    <div className={`capstone-process-step-heading ${headingClassName}`}>
      <button type="button" className="capstone-process-step-toggle" aria-label={`${open ? '折叠' : '展开'}步骤：${title}`} aria-expanded={open} aria-controls={bodyId} onClick={() => {
        const value = !open; setOpen(value); saveProcessStepOpen(storageKey, id, value)
      }}><ChevronRight aria-hidden="true" /></button>
      {heading}
    </div>
    {!open && summary && <p className="capstone-process-step-preview"><span>{summary.length > 180 ? `${summary.slice(0, 180)}…` : summary}</span></p>}
    <div id={bodyId} className="capstone-process-step-body" hidden={!open}>{children}</div>
  </>
}

export function ProcessFoldControls({ onChange }: { onChange: (open: boolean) => void }) {
  return <span className="capstone-process-controls" role="group" aria-label="步骤显示">
    <button type="button" title="展开全部步骤" aria-label="展开全部步骤" onClick={event => { event.preventDefault(); event.stopPropagation(); onChange(true) }}><ChevronsUpDown aria-hidden="true" /></button>
    <button type="button" title="折叠全部步骤" aria-label="折叠全部步骤" onClick={event => { event.preventDefault(); event.stopPropagation(); onChange(false) }}><ChevronsDownUp aria-hidden="true" /></button>
  </span>
}

export function ProcessDetailGroup({ id, title, storageKey, defaultExpanded = false, children, className = '', foldCommand }: { id: string; title: string; storageKey: string; defaultExpanded?: boolean; children: ReactNode; className?: string; foldCommand?: ProcessFoldCommand }) {
  const [open, setOpen] = useState(() => readProcessStepOpen(storageKey, `detail:${id}`, defaultExpanded))
  useEffect(() => {
    if (!foldCommand) return
    setOpen(foldCommand.open); saveProcessStepOpen(storageKey, `detail:${id}`, foldCommand.open)
  }, [foldCommand, id, storageKey])
  return <details className={`capstone-process-detail-group ${className}`} open={open} onToggle={event => {
    const value = event.currentTarget.open
    if (!event.currentTarget.isConnected || value === open) return
    setOpen(value); saveProcessStepOpen(storageKey, `detail:${id}`, value)
  }}><summary><ChevronRight className="capstone-process-detail-chevron" aria-hidden="true" />{title}</summary><div>{children}</div></details>
}
