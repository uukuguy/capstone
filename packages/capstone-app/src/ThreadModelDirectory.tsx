import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Database, X } from 'lucide-react'
import type { ThreadCatalogModel } from './threadCatalog'
import type { ModelWorkspace } from './threadModelWorkspace'

type Props = {
  models: ThreadCatalogModel[]
  currentModelId: string
  target: string
  disabled: boolean
  pending: boolean
  onTargetChange: (value: string) => void
  onSwitch: (modelId: string) => void
  workspace?: ModelWorkspace | null
  onActivate?: (entryId: string) => void
  onClose?: (entryId: string) => void
  embedded?: boolean
}

const modelOrder = new Intl.Collator('en', { numeric: true, sensitivity: 'base' })

/** Browsing is local; opening a model uses the existing Thread command path. */
export default function ThreadModelDirectory(props: Props) {
  return props.workspace ? <OpenedModelMenu {...props} workspace={props.workspace} /> : <RegisteredModelDirectory {...props} />
}

function OpenedModelMenu(props: Props & { workspace: ModelWorkspace }) {
  const [open, setOpen] = useState(false)
  const [directory, setDirectory] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const id = useId()
  const current = props.workspace.models.find((item) => item.entryId === props.workspace.currentEntryId)!
  const disabled = props.disabled || props.pending || Boolean(props.workspace.blockedReason)
  const close = () => { setOpen(false); setDirectory(false); trigger.current?.focus() }
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !root.current?.contains(event.target)) { setOpen(false); setDirectory(false) } }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])
  return <div className="thread-model-directory thread-opened-models" ref={root} onKeyDown={(event) => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close() }
  }} onBlur={(event) => { if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setDirectory(false) } }}>
    <button ref={trigger} type="button" className="thread-settings-trigger thread-model-trigger" aria-label={`当前模型：${current.displayName}`} title="已打开的电网模型" aria-expanded={open} aria-controls={id}
      onClick={() => { setOpen(!open); setDirectory(false) }}><Database aria-hidden="true" /><span>{current.displayName}</span><ChevronDown aria-hidden="true" /></button>
    {open && <section id={id} className="thread-directory-panel thread-opened-panel" aria-label="已打开电网模型">
      {directory ? <><button type="button" className="thread-model-back" onClick={() => setDirectory(false)}>返回已打开模型</button>
        <RegisteredModelDirectory {...props} embedded onSwitch={(modelId) => { props.onSwitch(modelId); close() }} /></> : <>
        <div className="thread-opened-list">{props.workspace.models.map((model) => <div key={model.entryId} className="thread-opened-row">
          <button type="button" className="thread-opened-select" aria-label={`设为当前模型：${model.displayName}`} aria-pressed={model.entryId === current.entryId} disabled={disabled}
            onClick={() => { props.onActivate?.(model.entryId); close() }}><span className="thread-opened-check">{model.entryId === current.entryId && <Check aria-hidden="true" />}</span><span>{model.displayName}</span></button>
          <button type="button" className="thread-opened-close" aria-label={`关闭 ${model.displayName}`} title={props.workspace.models.length === 1 ? '会话至少保留一个模型' : `关闭 ${model.displayName}`}
            disabled={disabled || props.workspace.models.length === 1} onClick={() => { props.onClose?.(model.entryId); close() }}><X aria-hidden="true" /></button>
        </div>)}</div>
        <button type="button" className="thread-model-open-other" disabled={disabled} onClick={() => setDirectory(true)}>打开其他模型…</button>
      </>}
    </section>}
  </div>
}

function RegisteredModelDirectory({ models, currentModelId, target, disabled, pending, onTargetChange, onSwitch, embedded = false }: Props) {
  const [open, setOpen] = useState(embedded)
  const [query, setQuery] = useState('')
  const [family, setFamily] = useState('')
  const [panelHeight, setPanelHeight] = useState(420)
  const opener = useRef<HTMLButtonElement>(null)
  const container = useRef<HTMLDivElement>(null)
  const search = useRef<HTMLInputElement>(null)
  const keyboardBrowse = useRef(false)
  const previousModelId = useRef(currentModelId)
  const id = useId()
  useEffect(() => { if (open) search.current?.focus() }, [open])
  useEffect(() => {
    if (previousModelId.current === currentModelId) return
    previousModelId.current = currentModelId
    setOpen(false); setQuery(''); setFamily('')
  }, [currentModelId])
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
  const openModel = (modelId: string) => {
    const model = filtered.find((item) => item.modelId === modelId)
    if (disabled || pending || !model || model.available === false || modelId === currentModelId) return
    onSwitch(modelId)
    setOpen(false)
    opener.current?.focus()
  }

  return <div ref={container} className={`thread-model-directory${embedded ? ' is-embedded' : ''}`} onKeyDown={(event) => {
    if (open && event.key === 'Enter' && !(event.target instanceof HTMLButtonElement)) { event.preventDefault(); event.stopPropagation() }
    if (open && !embedded && event.key === 'Escape') { event.stopPropagation(); setOpen(false); opener.current?.focus() }
  }} onBlur={(event) => {
    if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    {!embedded && <button ref={opener} type="button" className="thread-settings-trigger thread-model-trigger" aria-label="模型目录" title="选择电网模型" aria-expanded={open} aria-controls={id}
      onClick={() => { keyboardBrowse.current = false; if (!open) onTargetChange(currentModelId); setOpen((value) => !value) }}><Database aria-hidden="true" /><span>模型</span><ChevronDown aria-hidden="true" /></button>}
    {(open || embedded) && <section id={id} className="thread-directory-panel" style={{ maxHeight: panelHeight }} aria-label="已注册电网模型目录">
      <div className="thread-directory-filters">
        <input ref={search} type="search" aria-label="搜索电网模型" placeholder="搜索模型名称或 ID" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="模型引擎" value={family} onChange={(event) => setFamily(event.target.value)}>
          <option value="">全部引擎</option>{families.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </div>
      <p className="thread-directory-count" role="status">{filtered.length} / {models.length} 个已注册模型 · 按引擎、模型 ID 排序</p>
      {filtered.length ? <select size={Math.max(2, Math.min(6, filtered.length))} aria-label="目标电网模型" value={chosen ? target : ''} disabled={disabled}
        onPointerDown={() => { keyboardBrowse.current = false }}
        onKeyDown={(event) => {
          if (event.key.length === 1 || ['ArrowDown', 'ArrowUp', 'Home', 'End', 'PageDown', 'PageUp'].includes(event.key)) keyboardBrowse.current = true
          if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); openModel(event.currentTarget.value) }
        }}
        onChange={(event) => { onTargetChange(event.target.value); if (!keyboardBrowse.current) openModel(event.target.value) }}>
        <option value="" disabled hidden>请选择模型</option>
        {filtered.map((model) => <option key={model.modelId} value={model.modelId} disabled={model.available === false}>
          {model.modelId}{model.displayName !== model.modelId ? ` · ${model.displayName}` : ''} · {model.implementationFamily}{model.modelId === currentModelId ? ' · 当前模型' : ''}{model.available === false ? ` · ${modelUnavailableCopy(model.unavailableReason)}` : ''}
        </option>)}
      </select> : <p className="thread-directory-empty">没有匹配的已注册模型。请缩短搜索词或选择全部引擎。</p>}
      <div className="thread-directory-footer">
        <span>{embedded ? '选择后打开并设为当前模型' : pending ? '切换将在下一 Turn 激活' : '也可以在对话中输入“打开 模型 ID”。'}</span>
      </div>
    </section>}
  </div>
}

export function modelUnavailableCopy(reason?: string): string {
  switch (reason) {
    case 'diagram_limit': return '超出完整拓扑显示容量'
    case 'diagram_invalid': return '拓扑数据未通过校验'
    case 'worker_unavailable': return '模型服务未就绪'
    default: return '模型当前不可用'
  }
}
