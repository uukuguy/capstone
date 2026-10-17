import { useId, useLayoutEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/** One presentation container; readers and result projections retain their existing owners. */
export default function AnswerDetailSheet({ title, answerLabel, onClose, children }: {
  title: string; answerLabel: string; onClose: () => void; children: ReactNode
}) {
  const titleId = useId()
  const descriptionId = useId()
  const close = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const overflow = document.body.style.overflow
    const layer = panel.current?.closest('.answer-detail-layer')
    const siblings = [...document.body.children].filter((item): item is HTMLElement => item instanceof HTMLElement && item !== layer)
      .map(item => ({item, inert:item.inert}))
    for (const {item} of siblings) item.inert = true
    document.body.style.overflow = 'hidden'
    close.current?.focus()
    return () => {
      for (const {item,inert} of siblings) item.inert = inert
      document.body.style.overflow = overflow
      if (trigger?.isConnected) trigger.focus({ preventScroll: true })
    }
  }, [])
  return createPortal(<div className="answer-detail-layer">
    <div className="answer-detail-backdrop" aria-hidden="true" onClick={onClose} />
    <section ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}
      className="answer-detail-sheet" onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onClose() }
        if (event.key === 'Tab') {
          const items = [...(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary,[tabindex="0"]') || [])]
            .filter(item => !item.closest('[hidden]') && (!item.closest('details:not([open])') || item.tagName === 'SUMMARY'))
          const first = items[0], last = items.at(-1)
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
        }
      }}>
      <header className="answer-detail-heading"><div><h2 id={titleId}>{title}</h2><p id={descriptionId}>所属回答：{answerLabel}</p></div>
        <button ref={close} type="button" aria-label={`关闭${title}`} onClick={onClose}><X aria-hidden="true" /></button>
      </header>
      <div className="answer-detail-content">{children}</div>
    </section>
  </div>, document.body)
}
