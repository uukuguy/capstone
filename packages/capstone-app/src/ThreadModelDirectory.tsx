import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { ChevronDown, Database } from 'lucide-react'
import type { ThreadCatalogModel } from './threadCatalog'

type Props = {
  models: ThreadCatalogModel[]
  currentModelId: string
  target: string
  disabled: boolean
  pending: boolean
  onTargetChange: (value: string) => void
  onSwitch: () => void
}

const modelOrder = new Intl.Collator('en', { numeric: true, sensitivity: 'base' })

/** Browsing is local; opening a model uses the existing Thread command path. */
export default function ThreadModelDirectory({ models, currentModelId, target, disabled, pending, onTargetChange, onSwitch }: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [family, setFamily] = useState('')
  const [panelHeight, setPanelHeight] = useState(420)
  const opener = useRef<HTMLButtonElement>(null)
  const container = useRef<HTMLDivElement>(null)
  const search = useRef<HTMLInputElement>(null)
  const id = useId()
  useEffect(() => { if (open) search.current?.focus() }, [open])
  useEffect(() => { setOpen(false); setQuery(''); setFamily('') }, [currentModelId])
  useLayoutEffect(() => {
    if (!open) return
    const resizePanel = () => {
      const composer = container.current?.closest('.capstone-composer-root')
      const clip = container.current?.closest('.capstone-assistant-thread')
      if (!composer) return
      const top = composer.getBoundingClientRect().top
      const boundary = Math.max(0, clip?.getBoundingClientRect().top || 0)
      setPanelHeight(Math.max(0, Math.min(420, top - boundary - 12)))
    }
    resizePanel()
    window.addEventListener('resize', resizePanel)
    window.addEventListener('scroll', resizePanel, true)
    return () => { window.removeEventListener('resize', resizePanel); window.removeEventListener('scroll', resizePanel, true) }
  }, [open])
  useEffect(() => {
    if (!open) return
    const dismiss = (event: PointerEvent) => {
      if (event.target instanceof Node && !container.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', dismiss, true)
    return () => document.removeEventListener('pointerdown', dismiss, true)
  }, [open])
  const families = [...new Set(models.map((model) => model.implementationFamily))].sort()
  const normalized = query.trim().toLocaleLowerCase()
  const filtered = models.filter((model) => (!family || model.implementationFamily === family) &&
    `${model.modelId} ${model.displayName}`.toLocaleLowerCase().includes(normalized))
    .sort((left, right) => modelOrder.compare(left.implementationFamily, right.implementationFamily) ||
      modelOrder.compare(left.modelId, right.modelId) || left.modelId.localeCompare(right.modelId))
  const chosen = filtered.find((model) => model.modelId === target)

  return <div ref={container} className="thread-model-directory" onKeyDown={(event) => {
    if (open && event.key === 'Enter' && !(event.target instanceof HTMLButtonElement)) { event.preventDefault(); event.stopPropagation() }
    if (open && event.key === 'Escape') { event.stopPropagation(); setOpen(false); opener.current?.focus() }
  }} onBlur={(event) => {
    if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    <button ref={opener} type="button" className="thread-settings-trigger thread-model-trigger" aria-label="模型目录" title="选择电网模型" aria-expanded={open} aria-controls={id}
      onClick={() => setOpen((value) => !value)}><Database aria-hidden="true" /><span>模型</span><ChevronDown aria-hidden="true" /></button>
    {open && <section id={id} className="thread-directory-panel" style={{ maxHeight: panelHeight }} aria-label="已注册电网模型目录">
      <div className="thread-directory-filters">
        <input ref={search} type="search" aria-label="搜索电网模型" placeholder="搜索模型名称或 ID" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="模型引擎" value={family} onChange={(event) => setFamily(event.target.value)}>
          <option value="">全部引擎</option>{families.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </div>
      <p className="thread-directory-count" role="status">{filtered.length} / {models.length} 个已注册模型 · 按引擎、模型 ID 排序</p>
      {filtered.length ? <select size={Math.max(2, Math.min(6, filtered.length))} aria-label="目标电网模型" value={chosen ? target : ''} disabled={disabled}
        onChange={(event) => onTargetChange(event.target.value)}>
        <option value="" disabled hidden>请选择模型</option>
        {filtered.map((model) => <option key={model.modelId} value={model.modelId} disabled={model.available === false}>
          {model.modelId}{model.displayName !== model.modelId ? ` · ${model.displayName}` : ''} · {model.implementationFamily}{model.modelId === currentModelId ? ' · 当前模型' : ''}{model.available === false ? ` · 不可用 (${model.unavailableReason || 'worker unavailable'})` : ''}
        </option>)}
      </select> : <p className="thread-directory-empty">没有匹配的已注册模型。请缩短搜索词或选择全部引擎。</p>}
      <div className="thread-directory-footer"><button type="button" className="thread-control-button"
        disabled={disabled || !chosen || chosen.available === false || target === currentModelId} onClick={onSwitch}>切换模型</button>
        <span>{pending ? '切换将在下一 Turn 激活' : '也可以在对话中输入“打开 模型 ID”。'}</span>
      </div>
    </section>}
  </div>
}
