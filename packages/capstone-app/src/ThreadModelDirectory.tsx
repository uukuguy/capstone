import { useEffect, useId, useRef, useState } from 'react'
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

/** Browsing is local; opening a model uses the existing Thread command path. */
export default function ThreadModelDirectory({ models, currentModelId, target, disabled, pending, onTargetChange, onSwitch }: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [family, setFamily] = useState('')
  const opener = useRef<HTMLButtonElement>(null)
  const search = useRef<HTMLInputElement>(null)
  const id = useId()
  useEffect(() => { if (open) search.current?.focus() }, [open])
  useEffect(() => { setOpen(false); setQuery(''); setFamily('') }, [currentModelId])
  const families = [...new Set(models.map((model) => model.implementationFamily))].sort()
  const normalized = query.trim().toLocaleLowerCase()
  const filtered = models.filter((model) => (!family || model.implementationFamily === family) &&
    `${model.modelId} ${model.displayName}`.toLocaleLowerCase().includes(normalized))
  const chosen = filtered.find((model) => model.modelId === target)

  return <div className="thread-model-directory" onKeyDown={(event) => {
    if (open && event.key === 'Escape') { event.stopPropagation(); setOpen(false); opener.current?.focus() }
  }}>
    <button ref={opener} type="button" className="thread-control-button" aria-expanded={open} aria-controls={id}
      onClick={() => setOpen((value) => !value)}>模型目录</button>
    {open && <section id={id} className="thread-directory-panel" aria-label="已注册电网模型目录">
      <div className="thread-directory-filters">
        <input ref={search} type="search" aria-label="搜索电网模型" placeholder="搜索模型名称或 ID" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select aria-label="模型引擎" value={family} onChange={(event) => setFamily(event.target.value)}>
          <option value="">全部引擎</option>{families.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </div>
      <p className="thread-directory-count" role="status">{filtered.length} / {models.length} 个已注册模型</p>
      {filtered.length ? <select size={Math.max(2, Math.min(6, filtered.length))} aria-label="目标电网模型" value={chosen ? target : ''} disabled={disabled}
        onChange={(event) => onTargetChange(event.target.value)}>
        <option value="" disabled hidden>请选择模型</option>
        {filtered.map((model) => <option key={model.modelId} value={model.modelId} disabled={model.available === false}>
          {model.displayName}{model.displayName !== model.modelId ? ` · ${model.modelId}` : ''} · {model.implementationFamily}{model.modelId === currentModelId ? ' · 当前模型' : ''}{model.available === false ? ` · 不可用 (${model.unavailableReason || 'worker unavailable'})` : ''}
        </option>)}
      </select> : <p className="thread-directory-empty">没有匹配的已注册模型。请缩短搜索词或选择全部引擎。</p>}
      <div className="thread-directory-footer"><button type="button" className="thread-control-button"
        disabled={disabled || !chosen || chosen.available === false || target === currentModelId} onClick={onSwitch}>切换模型</button>
        <span>{pending ? '切换将在下一 Turn 激活' : '也可以在对话中输入“打开 模型 ID”。'}</span>
      </div>
    </section>}
  </div>
}
